from typing import Union, List
from astroid import nodes

from edulint.linting.analyses.types import guess_type, Type
from edulint.linting.analyses.data_dependency import vars_in, modified_in
from edulint.linting.checkers.utils import has_more_assign_targets, is_chained_assignment

IMMUTABLE_TYPES = [Type.BOOL, Type.FLOAT, Type.INT, Type.STRING, Type.TUPLE]


def _can_be_mutable(node: nodes.NodeNG) -> bool:
    t = guess_type(node)
    return t is None or not t.has_only(IMMUTABLE_TYPES)


def _can_be_mutable_name(node: Union[nodes.Name, nodes.AssignName]) -> bool:
    if isinstance(node, nodes.Name):
        return _can_be_mutable(node)

    assert isinstance(node, (nodes.AssignName))

    if isinstance(node.parent, (nodes.AugAssign, nodes.AnnAssign)):
        return _can_be_mutable(node.parent.value)
    elif isinstance(node.parent, nodes.Assign):
        if is_chained_assignment(node.parent):
            return True

        if not has_more_assign_targets(node.parent):
            return _can_be_mutable(node.parent.value)

        for val in node.parent.value.get_children():
            if _can_be_mutable(val):
                return True

    return False


def may_contain_mutable_var(node: nodes.NodeNG) -> bool:
    "If this function returns `False`, then we are sure that the node does not contain any mutable vars."
    for _, var_nodes in vars_in(node).items():
        for node in var_nodes:
            if isinstance(node, (nodes.Name, nodes.AssignName)) and _can_be_mutable_name(node):
                return True

    return False


def vars_from_node_may_be_modified_in(node: nodes.NodeNG, nodes: List[nodes.NodeNG]) -> bool:
    "Note: may not work when there are some global variables in `node`."
    return may_contain_mutable_var(node) or modified_in(list(vars_in(node).keys()), nodes)
