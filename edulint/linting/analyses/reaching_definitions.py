from typing import List, Union, Set, Optional, Tuple

from astroid import nodes

from edulint.linting.analyses.cfg.graph import CFGLoc
from edulint.linting.analyses.cfg.utils import (
    predecessors_from_loc,
    successors_from_loc,
    successors_from_locs,
    syntactic_children_locs_from,
    get_cfg_loc,
    get_first_locs_after,
)
from edulint.linting.analyses.variable_scope import ScopeNode, VarName
from edulint.linting.analyses.variable_modification import VarEventType


def vars_in(
    node: Union[nodes.NodeNG, List[nodes.NodeNG]], events: Optional[Set[VarEventType]] = None
) -> Set[Tuple[str, ScopeNode]]:
    result = set()

    first = node[0] if isinstance(node, list) else node
    for loc in syntactic_children_locs_from(get_cfg_loc(first), node):
        for varname, scope, event in loc.var_events:
            if events is None or event in events:
                result.add((varname, scope))
    return result


def get_scope(varname: VarName, loc: CFGLoc) -> Optional[ScopeNode]:
    for loc in predecessors_from_loc(loc, include_start=True):
        for loc_varname, scope, _event in loc.var_events:
            if varname == loc_varname:
                return scope
    for node in loc.node.root().body:
        for loc_varname, scope, _event in node.cfg_loc.var_events:
            if varname == loc_varname:
                return scope
        if isinstance(node, nodes.ClassDef):
            for node in node.body:
                for loc_varname, scope, _event in node.cfg_loc.var_events:
                    if varname == loc_varname:
                        return scope
    return None


def is_changed_between(varname: str, before_loc: CFGLoc, after_locs: List[CFGLoc]) -> bool:
    scope = get_scope(varname, before_loc)
    assert scope is not None, f"but {varname}"

    for after_loc in after_locs:
        for loc in predecessors_from_loc(
            after_loc, stop_on_loc=lambda loc: loc == before_loc, include_start=True
        ):
            for loc_varname, loc_scope, event in loc.var_events:
                if loc_varname == varname and (loc_scope != scope or event != VarEventType.READ):
                    return True
    return False


def get_vars_defined_before(core):
    result = set()

    first_loc = get_cfg_loc(core[0] if isinstance(core, list) else core)

    vars = {
        (varname, scope)
        for loc in syntactic_children_locs_from(first_loc, core)
        for sub_loc in loc.node.sub_locs
        for varname, scope, event in sub_loc.var_events
        if event == VarEventType.READ
    }

    # FIXME counts all read variables, including avars
    for varname, scope in vars:
        for loc in successors_from_loc(
            first_loc,
            stop_on_loc=lambda loc: all(
                varname != loc_varname
                or scope != loc_scope
                or event in {VarEventType.ASSIGN, VarEventType.REASSIGN}
                for sub_loc in loc.node.sub_locs
                for loc_varname, loc_scope, event in sub_loc.var_events
            ),
            include_start=True,
            include_end=True,
        ):
            for sub_loc in loc.node.sub_locs:
                for loc_varname, loc_scope, event in sub_loc.var_events:
                    if event == VarEventType.READ:
                        result.add((varname, scope))

    return result


def get_vars_used_after(core) -> Set[Tuple[str, ScopeNode]]:
    result = set()
    core_subs = (
        [[c.sub_locs[i] for c in core] for i in range(len(core[0].sub_locs))]
        if isinstance(core, list)
        else core.sub_locs
    )

    first_locs_after = [loc for core_sub in core_subs for loc in get_first_locs_after(core_sub)]

    vars = {
        var
        for core_sub in core_subs
        for var in vars_in(
            [c.node for c in core_sub] if isinstance(core_sub, list) else core_sub.node,
            {VarEventType.ASSIGN, VarEventType.REASSIGN, VarEventType.MODIFY},
        )
    }
    for varname, scope in vars:
        for loc in successors_from_locs(
            first_locs_after,
            stop_on_loc=lambda loc: any(
                varname == loc_vn
                and scope == loc_scope
                and event in {VarEventType.ASSIGN, VarEventType.REASSIGN}
                for loc_vn, loc_scope, event in loc.var_events
            ),
            include_start=True,
            include_end=True,
        ):
            for loc_varname, loc_scope, event in loc.var_events:
                if loc_varname == varname and loc_scope == scope and event == VarEventType.READ:
                    result.add((varname, scope))

    return result


def get_control_statements(core):
    result = []
    first_loc = get_cfg_loc(core[0] if isinstance(core, list) else core)
    for loc in syntactic_children_locs_from(first_loc, core):
        if isinstance(loc.node, (nodes.Return, nodes.Break, nodes.Continue)):
            result.append(loc.node)
    return result
