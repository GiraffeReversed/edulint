from typing import Union, List, Set, Optional
from astroid import nodes

from edulint.linting.analyses.types import guess_type, Type
from edulint.linting.analyses.data_dependency import vars_in, modified_in, get_events_in
from edulint.linting.checkers.utils import has_more_assign_targets, is_chained_assignment
from edulint.linting.analyses.var_events import VarEventType, VarEvent

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


def _get_body_of_called_function(definition: VarEvent) -> Optional[List[nodes.NodeNG]]:
    if isinstance(definition.node, nodes.FunctionDef):
        return definition.node.body

    if (
        not isinstance(definition.node.parent, (nodes.AnnAssign, nodes.Assign))
        or is_chained_assignment(definition.node.parent)
        or has_more_assign_targets(definition.node.parent)
        or not isinstance(definition.node.parent.value, nodes.Lambda)
    ):
        return None

    return [definition.node.parent.value]


def _may_contain_global_variable_modified_in_function(
    node: nodes.NodeNG, nodes_: List[nodes.NodeNG], checked_function_names: Set[str]
) -> bool:
    for event in get_events_in(nodes_, [VarEventType.READ]):
        if not isinstance(event.node.parent, nodes.Call) or event.node != event.node.parent.func:
            continue

        for definition in event.definitions:
            func_name = event.node.name
            if func_name in checked_function_names:
                continue

            checked_function_names.add(func_name)
            body = _get_body_of_called_function(definition)

            if (
                body is None
                or _vars_from_node_may_be_directly_modified_in(node, body)
                or _may_contain_global_variable_modified_in_function(
                    node, body, checked_function_names
                )
            ):
                return True

    return False


def _vars_from_node_may_be_directly_modified_in(
    node: nodes.NodeNG, nodes_: List[nodes.NodeNG]
) -> bool:
    return may_contain_mutable_var(node) or modified_in(list(vars_in(node).keys()), nodes_)


def vars_from_node_may_be_modified_in(node: nodes.NodeNG, nodes_: List[nodes.NodeNG]) -> bool:
    """If returns `False`, then vars from `node` are not modified in `nodes` for sure."""
    return _vars_from_node_may_be_directly_modified_in(
        node, nodes_
    ) or _may_contain_global_variable_modified_in_function(node, nodes_, set())
