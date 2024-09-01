from typing import List, Union, Set, Optional, Dict, Tuple
from collections import defaultdict

from astroid import nodes

from edulint.linting.analyses.cfg.graph import CFGLoc, CFGBlock
from edulint.linting.analyses.cfg.utils import (
    successor_blocks_from_locs,
    predecessors_from_loc,
    syntactic_children_locs,
    syntactic_children_locs_from,
    get_cfg_loc,
)
from edulint.linting.analyses.var_events import VarEventType, Variable, VarEvent, strip_to_name


MODIFYING_EVENTS = (VarEventType.ASSIGN, VarEventType.REASSIGN, VarEventType.MODIFY)
KILLING_EVENTS = (
    VarEventType.ASSIGN,
    VarEventType.REASSIGN,
    VarEventType.DELETE,
    VarEventType.MODIFY,
)
GENERATING_EVENTS = (VarEventType.READ, VarEventType.MODIFY)


### collectors


def collect_gens_kill(
    block: CFGBlock,
) -> Tuple[Dict[Variable, List[VarEvent]], Dict[Variable, List[VarEvent]]]:
    gens, kill = defaultdict(list), defaultdict(list)
    for loc in block.locs:
        for var, event in loc.var_events.all():
            if event.type in GENERATING_EVENTS:
                if var not in kill:
                    gens[var].append(event)
                else:
                    assert len(kill[var]) == 1
                    kill_event = kill[var][0]

                    if kill_event not in event.definitions:
                        event.definitions.append(kill_event)

                    if event not in kill_event.uses:
                        kill_event.uses.append(event)

            if event.type in KILLING_EVENTS:
                kill[var] = [event]

    return gens, kill


def kills_from_parents(
    block: CFGBlock,
    kills: Dict[CFGBlock, Dict[Variable, List[Tuple[CFGLoc, VarEvent]]]],
    parent_scope_kills: Dict[Variable, List[Tuple[CFGLoc, VarEvent]]],
) -> Dict[Variable, List[Tuple[CFGLoc, VarEvent]]]:
    if len(block.predecessors) == 0:
        return parent_scope_kills

    result = defaultdict(list)
    for edge in block.predecessors:
        parent = edge.source
        if not parent.reachable:
            continue
        for var, es in kills[parent].items():
            result[var].extend(es)
    return result


def collect_reaching_definitions(
    node: Union[nodes.Module, nodes.Arguments],
    parent_scope_kills: Dict[Variable, List[Tuple[CFGLoc, nodes.NodeNG]]] = None,
) -> None:
    parent_scope_kills = parent_scope_kills if parent_scope_kills is not None else {}

    original_gens_kills = {}
    blocks = []
    for block, start, end in successor_blocks_from_locs([node.cfg_loc], include_start=True):
        assert start == 0 and end == len(block.locs)
        original_gens_kills[block] = collect_gens_kill(block)

        blocks.append(block)

    computed_kills = {
        block: defaultdict(list, {var: k.copy() for var, k in kills.items()})
        for block, (_gens, kills) in original_gens_kills.items()
    }

    changed = True
    while changed:
        changed = False

        for block in blocks:
            parent_kills = kills_from_parents(block, computed_kills, parent_scope_kills)
            gens, original_kill = original_gens_kills[block]
            computed_kill = computed_kills[block]

            for var, es in parent_kills.items():
                # this block does not kill the parent's value
                if var not in original_kill:
                    for kill_event in es:
                        # if the kill was not added already
                        if kill_event not in computed_kill[var]:
                            computed_kill[var].append(kill_event)
                            changed = True

                for gen_event in gens.get(var, []):
                    for kill_event in es:
                        if kill_event not in gen_event.definitions:
                            gen_event.definitions.append(kill_event)
                        if gen_event not in kill_event.uses:
                            kill_event.uses.append(gen_event)

    for block in blocks:
        for loc in block.locs:
            if isinstance(loc.node, nodes.FunctionDef):
                collect_reaching_definitions(loc.node.args, computed_kills[block])
            elif isinstance(loc.node, nodes.ClassDef):
                for class_node in loc.node.body:
                    if isinstance(class_node, nodes.FunctionDef):
                        collect_reaching_definitions(class_node.args, computed_kills[block])


### var getters


def vars_in(
    node: Union[nodes.NodeNG, List[nodes.NodeNG]], event_types: Optional[Set[VarEventType]] = None
) -> Dict[Variable, List[nodes.NodeNG]]:
    result = {}

    if isinstance(node, nodes.NodeNG):
        loc_node = get_cfg_loc(node).node
    else:
        loc_node = node

    for loc in syntactic_children_locs(loc_node):
        for var, event in loc.var_events.all():
            if event_types is None or event.type in event_types:
                if loc_node == node or (event.node == node or node in event.node.node_ancestors()):
                    result[var] = event.node
    return result


def name_to_var(name: str, node: nodes.NodeNG):
    start = get_cfg_loc(node)
    for loc in syntactic_children_locs_from(start, node):
        for var, events in loc.var_events.items():
            event_scope = events[0].node.scope()
            if var.name == name and event_scope == node.scope():
                return var
    return None


def node_to_var(node: nodes.NodeNG):
    loc = get_cfg_loc(node)
    for var, event in loc.var_events.all():
        if event.node == node:
            return var
    return None


def _get_matching_superpart(var_node: nodes.NodeNG, super_node: nodes.NodeNG):
    stripped = strip_to_name(super_node)
    while stripped != super_node:
        stripped = stripped.parent
        var_node = var_node.parent

        if not isinstance(var_node, type(stripped)):
            return None

        if isinstance(stripped, (nodes.Attribute, nodes.AssignAttr, nodes.DelAttr)):
            if stripped.attrname != var_node.attrname:
                return None

        elif isinstance(stripped, nodes.Subscript):
            stripped_vars = set(vars_in(stripped.slice).keys())
            node_vars = set(vars_in(var_node.slice).keys())
            stripped_events = get_events_by_var(stripped_vars, [stripped.slice])
            node_events = get_events_by_var(node_vars, [var_node.slice])
            if list(stripped_events.keys()) != list(node_events.keys()):
                return None

            for var in stripped_events.keys():
                if [e.definitions for e in stripped_events[var]] != [
                    e.definitions for e in node_events[var]
                ]:
                    return None
        else:
            assert False, "unreachable, but " + str(type(stripped))
    return var_node


def filter_events_for(node: nodes.Attribute, events: List[VarEvent]) -> List[VarEvent]:
    if isinstance(node, (nodes.Name, nodes.AssignName)):
        return events

    result = []
    for event in events:
        superpart = _get_matching_superpart(event.node, node)
        if superpart is not None:
            result.append(VarEvent(event.var, superpart, event.type, None, None))
    return result


### event checkers


def is_changed_between(var: Variable, before_loc: CFGLoc, after_locs: List[CFGLoc]) -> bool:
    for after_loc in after_locs:
        for loc in predecessors_from_loc(
            after_loc, stop_on_loc=lambda loc: loc == before_loc, include_start=True
        ):
            for event in loc.var_events[var]:
                if event.type != VarEventType.READ:
                    return True
    return False


def get_events_for(
    vars: List[Variable],
    nodes: List[nodes.NodeNG],
    event_types: Optional[List[VarEventType]] = None,
):
    if len(nodes) == 0:
        return

    loc_nodes = [get_cfg_loc(n).node for n in nodes]
    check_ancestors = all(n == ln for n, ln in zip(nodes, loc_nodes))
    for loc in syntactic_children_locs(loc_nodes, explore_functions=True, explore_classes=True):
        for var in vars:
            for event in loc.var_events.for_var(var):
                if (event_types is None or event.type in event_types) and (
                    not check_ancestors
                    or any(event.node == n or n in event.node.node_ancestors() for n in nodes)
                ):
                    yield event


def get_events_by_var(
    vars: List[Variable],
    nodes: List[nodes.NodeNG],
    event_types: Optional[List[VarEventType]] = None,
):
    result = defaultdict(list)
    for event in get_events_for(vars, nodes, event_types):
        result[event.var].append(event)
    return result


def modified_in(vars: List[Variable], nodes: List[nodes.NodeNG]) -> bool:
    # just check whether there is such an event
    for _ in get_events_for(vars, nodes, MODIFYING_EVENTS):
        return True
    return False


def get_vars_defined_before(core) -> Dict[Variable, Set[nodes.NodeNG]]:
    # FIXME counts all read variables, including avars
    result = defaultdict(set)
    for i in range(len(core[0].sub_locs)):
        core_sub_locs = [c.sub_locs[i] for c in core]
        children_locs = set(
            syntactic_children_locs_from(core_sub_locs[0], [loc.node for loc in core_sub_locs])
        )
        for loc in children_locs:
            for var, event in loc.var_events.all():
                # if event.type not in GENERATING_EVENTS:
                #     continue
                for def_event in event.definitions:
                    if get_cfg_loc(def_event.node) not in children_locs:
                        result[var].add(def_event.node)
    return result


def get_vars_used_after(core) -> Dict[Variable, Set[nodes.NodeNG]]:
    """DANGER: variables used in core are not returned, even if core is in a loop"""
    result = defaultdict(set)
    for i in range(len(core[0].sub_locs)):
        core_sub_locs = [c.sub_locs[i] for c in core]
        children_locs = set(
            syntactic_children_locs_from(core_sub_locs[0], [loc.node for loc in core_sub_locs])
        )
        for loc in children_locs:
            for var, event in loc.var_events.all():
                # if event.type not in MODIFYING_EVENTS:
                #     continue
                for use_event in event.uses:
                    if get_cfg_loc(use_event.node) not in children_locs:
                        result[var].add(use_event.node)
    return result


def get_control_statements(core):
    result = []
    first_loc = get_cfg_loc(core[0] if isinstance(core, list) else core)
    for loc in syntactic_children_locs_from(first_loc, core):
        if isinstance(loc.node, (nodes.Return, nodes.Break, nodes.Continue)):
            result.append(loc.node)
    return result
