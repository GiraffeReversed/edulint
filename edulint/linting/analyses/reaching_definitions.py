from typing import List, Union, Set, Optional, Dict, Tuple
from collections import defaultdict

from astroid import nodes

from edulint.linting.analyses.cfg.graph import CFGLoc, CFGBlock
from edulint.linting.analyses.cfg.utils import (
    successor_blocks_from_locs,
    predecessors_from_loc,
    syntactic_children_locs_from,
    get_cfg_loc,
)
from edulint.linting.analyses.variable_scope import Variable
from edulint.linting.analyses.variable_modification import VarEventType


MODIFYING_EVENTS = (VarEventType.ASSIGN, VarEventType.REASSIGN, VarEventType.MODIFY)
KILLING_EVENTS = (
    VarEventType.ASSIGN,
    VarEventType.REASSIGN,
    VarEventType.DELETE,
    VarEventType.MODIFY,
)
GENERATING_EVENTS = (VarEventType.READ, VarEventType.MODIFY)


def collect_gens_kill(
    block: CFGBlock,
) -> Tuple[
    Dict[Variable, List[Tuple[CFGLoc, nodes.NodeNG]]],
    Dict[Variable, List[Tuple[CFGLoc, nodes.NodeNG]]],
]:
    gens, kill = defaultdict(list), defaultdict(list)
    for loc in block.locs:
        for var, events in loc.var_events.items():
            for event in events:
                if event.type in GENERATING_EVENTS:
                    if var not in kill:
                        gens[var].append((loc, event.node))
                    else:
                        assert len(kill[var]) == 1
                        kill_loc, kill_node = kill[var][0]
                        loc.definitions[event.node].add(kill_node)
                        kill_loc.uses[kill_node].add(event.node)

                if event.type in KILLING_EVENTS:
                    kill[var] = [(loc, event.node)]

    return gens, kill


def kills_from_parents(
    block: CFGBlock,
    gens_kill: Dict[
        CFGBlock,
        Tuple[
            Dict[Variable, List[Tuple[CFGLoc, nodes.NodeNG]]],
            Dict[Variable, List[Tuple[CFGLoc, nodes.NodeNG]]],
        ],
    ],
    parent_scope_kills: Dict[Variable, List[Tuple[CFGLoc, nodes.NodeNG]]],
) -> Dict[Variable, List[Tuple[CFGLoc, nodes.NodeNG]]]:
    if len(block.predecessors) == 0:
        return parent_scope_kills

    result = defaultdict(list)
    for edge in block.predecessors:
        parent = edge.source
        if not parent.reachable:
            continue
        kill = gens_kill[parent]
        for var, ns in kill.items():
            result[var].extend(ns)
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
        for block, (gens, kills) in original_gens_kills.items()
    }

    changed = True
    while changed:
        changed = False

        for block in blocks:
            parent_kills = kills_from_parents(block, computed_kills, parent_scope_kills)
            gens, original_kill = original_gens_kills[block]
            computed_kill = computed_kills[block]

            for var, ns in parent_kills.items():
                # this block does not kill the parent's value
                if var not in original_kill:
                    for def_loc_node in ns:
                        # if the kill was not added already
                        if def_loc_node not in computed_kill[var]:
                            computed_kill[var].append(def_loc_node)
                            changed = True

                for use_loc, use_node in gens.get(var, []):
                    for def_loc, def_node in ns:
                        use_loc.definitions[use_node].add(def_node)
                        def_loc.uses[def_node].add(use_node)

    for block in blocks:
        for loc in block.locs:
            if isinstance(loc.node, nodes.FunctionDef):
                collect_reaching_definitions(loc.node.args, computed_kills[block])
            elif isinstance(loc.node, nodes.ClassDef):
                for class_node in loc.node.body:
                    if isinstance(class_node, nodes.FunctionDef):
                        collect_reaching_definitions(class_node.args, computed_kills[block])


def vars_in(
    node: Union[nodes.NodeNG, List[nodes.NodeNG]], event_types: Optional[Set[VarEventType]] = None
) -> Dict[Variable, List[nodes.NodeNG]]:
    result = {}

    first = node[0] if isinstance(node, list) else node
    for loc in syntactic_children_locs_from(get_cfg_loc(first), node):
        for (varname, scope), events in loc.var_events.items():
            for event in events:
                if event_types is None or event.type in event_types:
                    result[(varname, scope)] = event.node
    return result


def is_changed_between(var: Variable, before_loc: CFGLoc, after_locs: List[CFGLoc]) -> bool:
    for after_loc in after_locs:
        for loc in predecessors_from_loc(
            after_loc, stop_on_loc=lambda loc: loc == before_loc, include_start=True
        ):
            for event in loc.var_events[var]:
                if event.type != VarEventType.READ:
                    return True
    return False


def node_to_var(node, loc):
    for var, events in loc.var_events.items():
        for event in events:
            if event.node == node:
                return var
    assert False, "unreachable"


def get_vars_defined_before(core) -> Dict[Variable, Set[nodes.NodeNG]]:
    # FIXME counts all read variables, including avars
    result = defaultdict(set)
    for i in range(len(core[0].sub_locs)):
        core_sub_locs = [c.sub_locs[i] for c in core]
        children_locs = set(
            syntactic_children_locs_from(core_sub_locs[0], [loc.node for loc in core_sub_locs])
        )
        for loc in children_locs:
            for use_node, definitions in loc.definitions.items():
                var = node_to_var(use_node, loc)
                for def_node in definitions:
                    if get_cfg_loc(def_node) not in children_locs:
                        result[var].add(def_node)
    return result


def get_vars_used_after(core) -> Dict[Variable, Set[nodes.NodeNG]]:
    result = defaultdict(set)
    for i in range(len(core[0].sub_locs)):
        core_sub_locs = [c.sub_locs[i] for c in core]
        children_locs = set(
            syntactic_children_locs_from(core_sub_locs[0], [loc.node for loc in core_sub_locs])
        )
        for loc in children_locs:
            for def_node, users in loc.uses.items():
                var = node_to_var(def_node, loc)
                for use_node in users:
                    if get_cfg_loc(use_node) not in children_locs:
                        result[var].add(use_node)
    return result


def get_control_statements(core):
    result = []
    first_loc = get_cfg_loc(core[0] if isinstance(core, list) else core)
    for loc in syntactic_children_locs_from(first_loc, core):
        if isinstance(loc.node, (nodes.Return, nodes.Break, nodes.Continue)):
            result.append(loc.node)
    return result
