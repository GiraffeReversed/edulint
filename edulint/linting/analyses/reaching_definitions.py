from typing import List, Union, Set, Optional, Dict
from collections import defaultdict

from astroid import nodes

from edulint.linting.analyses.cfg.graph import CFGLoc
from edulint.linting.analyses.cfg.utils import (
    predecessors_from_loc,
    successors_from_loc,
    successors_from_locs,
    syntactic_children_locs_from,
    get_cfg_loc,
    get_locs_in_and_after,
)
from edulint.linting.analyses.variable_scope import Variable
from edulint.linting.analyses.variable_modification import VarEventType


def vars_in(
    node: Union[nodes.NodeNG, List[nodes.NodeNG]], event_types: Optional[Set[VarEventType]] = None
) -> Set[Variable]:
    result = set()

    first = node[0] if isinstance(node, list) else node
    for loc in syntactic_children_locs_from(get_cfg_loc(first), node):
        for (varname, scope), events in loc.var_events.items():
            for event in events:
                if event_types is None or event.type in event_types:
                    result.add((varname, scope))
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


def get_vars_defined_before(core):
    result = set()

    first_loc = get_cfg_loc(core[0] if isinstance(core, list) else core)

    vars = {
        (varname, scope)
        for loc in syntactic_children_locs_from(first_loc, core)
        for sub_loc in loc.node.sub_locs
        for (varname, scope), events in sub_loc.var_events.items()
        for event in events
        if event.type == VarEventType.READ
    }

    # FIXME counts all read variables, including avars
    for varname, scope in vars:
        for loc in successors_from_loc(
            first_loc,
            stop_on_loc=lambda loc: all(
                event.type in {VarEventType.ASSIGN, VarEventType.REASSIGN}
                for sub_loc in loc.node.sub_locs
                for event in sub_loc.var_events[(varname, scope)]
            ),
            include_start=True,
            include_end=True,
        ):
            for sub_loc in loc.node.sub_locs:
                for (loc_varname, loc_scope), events in sub_loc.var_events.items():
                    for event in events:
                        if event.type == VarEventType.READ:
                            result.add((varname, scope))

    return result


MODIFYING_EVENTS = (VarEventType.ASSIGN, VarEventType.REASSIGN, VarEventType.MODIFY)


def get_vars_used_after(core) -> Dict[Variable, List[nodes.NodeNG]]:
    core_subs = (
        [[c.sub_locs[i] for c in core] for i in range(len(core[0].sub_locs))]
        if isinstance(core, list)
        else core.sub_locs
    )

    vars = set()
    first_locs_after = set()
    for core_sub in core_subs:
        for is_in, block, from_pos, to_pos in get_locs_in_and_after(core_sub):
            if is_in:
                for i in range(from_pos, to_pos):
                    loc = block.locs[i]
                    for (varname, scope), events in loc.var_events.items():
                        for event in events:
                            if event.type in MODIFYING_EVENTS:
                                vars.add((varname, scope))
            else:
                first_locs_after.add(block.locs[from_pos])

    result = defaultdict(list)
    for varname, scope in vars:
        for loc in successors_from_locs(
            first_locs_after,
            stop_on_loc=lambda loc: any(
                event.type in {VarEventType.ASSIGN, VarEventType.REASSIGN}
                for event in loc.var_events[(varname, scope)]
            ),
            include_start=True,
            include_end=True,
        ):
            for event in loc.var_events[(varname, scope)]:
                if event.type == VarEventType.READ:
                    result[(varname, scope)].append(loc.node)

    return dict(result)


def get_control_statements(core):
    result = []
    first_loc = get_cfg_loc(core[0] if isinstance(core, list) else core)
    for loc in syntactic_children_locs_from(first_loc, core):
        if isinstance(loc.node, (nodes.Return, nodes.Break, nodes.Continue)):
            result.append(loc.node)
    return result
