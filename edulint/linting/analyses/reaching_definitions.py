from typing import List, Union, Set

from astroid import nodes

from edulint.linting.analyses.cfg.graph import CFGLoc
from edulint.linting.analyses.cfg.utils import predecessors_from_loc  # , get_cfg_loc
from edulint.linting.analyses.variable_scope import ScopeNode, VarName
from edulint.linting.analyses.variable_modification import VarEventType
from edulint.linting.checkers.utils import BaseVisitor


class VarnameExtractor(BaseVisitor[None]):
    def __init__(self):
        super().__init__()
        self.varnames = set()

    def visit_name(self, node: nodes.Name) -> None:
        self.varnames.add(node.name)


def extract_varnames(node: Union[nodes.NodeNG, List[nodes.NodeNG]]) -> Set[str]:
    # alternatively implement using CFGLocs and related var_events
    nodes = node if isinstance(node, list) else [node]
    visitor = VarnameExtractor()
    visitor.visit_many(nodes)
    return visitor.varnames


def get_scope(varname: VarName, loc: CFGLoc) -> ScopeNode:
    for loc in predecessors_from_loc(loc, include_start=True):
        for loc_varname, scope, event in loc.var_events:
            if varname == loc_varname:
                return scope
    assert False, f"unreachable, but {varname}"


# def is_changed_between(varname: str, before: nodes.NodeNG, afters: List[nodes.NodeNG]):
#     before_loc = get_cfg_loc(before)
#     scope = get_scope(varname, before_loc)
#     for after in afters:
#         after_loc = get_cfg_loc(after)
def is_changed_between(varname: str, before_loc: CFGLoc, after_locs: List[CFGLoc]):
    scope = get_scope(varname, before_loc)
    for after_loc in after_locs:
        for loc in predecessors_from_loc(
            after_loc, stop_on=lambda loc: loc == before_loc, include_start=True
        ):
            for loc_varname, loc_scope, event in loc.var_events:
                if loc_varname == varname and (loc_scope != scope or event != VarEventType.READ):
                    return True
    return False


def get_vars_defined_before(core):
    return []  # TODO implement


def get_vars_used_after(core):
    return []  # TODO implement


def get_control_statements(core):
    return []  # TODO implement
