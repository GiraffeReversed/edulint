from typing import Union
from astroid import nodes

from edulint.linting.analyses.types import guess_type, Type
from edulint.linting.analyses.data_dependency import vars_in

IMMUTABLE_TYPES = [Type.BOOL, Type.FLOAT, Type.INT, Type.STRING, Type.TUPLE]


def _may_be_mutable(node: nodes.NodeNG) -> bool:
    t = guess_type(node)
    return t is None or not t.has_only(IMMUTABLE_TYPES)


def _may_be_mutable_name(node: Union[nodes.Name, nodes.AssignName]) -> bool:
    if isinstance(node, nodes.Name):
        return _may_be_mutable(node)

    assert isinstance(node, (nodes.AssignName))

    if isinstance(node.parent, (nodes.AugAssign, nodes.AnnAssign)):
        return _may_be_mutable(node.parent.value)
    elif isinstance(node.parent, nodes.Assign):
        if len(node.parent.targets) < 2:
            return _may_be_mutable(node.parent.value)

        for val in node.parent.value:
            if _may_be_mutable(val):
                return True

    return False


def may_contain_mutable_var(node: nodes.NodeNG) -> bool:
    for _, var_nodes in vars_in(node).items():
        for node in var_nodes:
            if isinstance(node, (nodes.Name, nodes.AssignName)) and _may_be_mutable_name(node):
                return True

    return False
