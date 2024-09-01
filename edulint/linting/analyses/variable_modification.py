import re

from astroid import nodes

from edulint.linting.analyses.cfg.utils import get_cfg_loc
from edulint.linting.analyses.variable_scope import ScopeListener
from edulint.linting.checkers.utils import is_builtin
from edulint.linting.analyses.var_events import (
    VarEventType,
    VarName,
    Variable,
    VarEvent,
    strip_to_name,
)


class VarModificationAnalysis:
    @staticmethod
    def collect(node: nodes.NodeNG):
        VarEventListener().visit(node)


class VarEventListener(ScopeListener[None]):
    NON_PURE_METHODS = re.compile(
        r"append|clear|extend|insert|pop|remove|reverse|sort|add|.*update|write"
    )

    def __init__(self):
        super().__init__()

    @staticmethod
    def may_be_unscoped(name: str, name_node: nodes.NodeNG, loc_node: nodes.NodeNG):
        if name.startswith("__"):
            return True
        if is_builtin(name_node, name):
            return True
        if (
            isinstance(name_node, nodes.Attribute)
            and isinstance(name_node.parent, nodes.Call)
            and name_node.parent.func == name_node
        ):
            return True

        for parent in name_node.node_ancestors():
            if parent == loc_node.parent:
                break
            if isinstance(parent, nodes.Call):  # and is_builtin(parent.func, name):
                return True

        return False

    def _add_var_event(self, name: VarName, name_node: nodes.NodeNG, action: VarEventType):
        loc = get_cfg_loc(name_node)
        scope = self._get_var_scope(name)
        # assert scope is not None or VarEventListener.may_be_unscoped(
        #     name, name_node, loc.node
        # ), f"but {name_node.as_string()}, {loc.node.as_string()}"
        if scope is not None:
            var = Variable(name, scope)
            loc.var_events.add(var, VarEvent(var, name_node, action))

    # @override
    def _init_var_in_scope(self, name: VarName, name_node: nodes.NodeNG, offset: int = 0) -> None:
        was_defined = name in self.stack[-1 + offset]
        super()._init_var_in_scope(name, name_node, offset)
        self._add_var_event(
            name, name_node, VarEventType.ASSIGN if not was_defined else VarEventType.REASSIGN
        )

    # @override
    def _del_var_from_scope(self, name: VarName, node: nodes.NodeNG):
        self._add_var_event(name, node, VarEventType.DELETE)
        super()._del_var_from_scope(name, node)

    # @override
    def _visit_assigned_to(self, node: nodes.NodeNG) -> None:
        super()._visit_assigned_to(node)

        stripped = strip_to_name(node)
        if stripped is None:
            return

        if isinstance(node, (nodes.AssignAttr, nodes.Subscript)):
            self._add_var_event(stripped.name, stripped, VarEventType.MODIFY)

    # @override
    def visit_augassign(self, node: nodes.AugAssign) -> None:
        stripped = strip_to_name(node.target)
        if stripped is not None:
            self._add_var_event(stripped.name, node, VarEventType.READ)

        super().visit_augassign(node)

    def visit_name(self, node: nodes.Name) -> None:
        self._add_var_event(node.name, node, VarEventType.READ)

    def visit_attribute(self, node: nodes.Attribute) -> None:
        stripped = strip_to_name(node)
        if (
            isinstance(node.parent, nodes.Call)
            and VarEventListener.NON_PURE_METHODS.match(node.attrname)
            and stripped is not None
        ):
            self._add_var_event(stripped.name, stripped, VarEventType.MODIFY)

        return self.visit_many(node.get_children())

    def visit_assignattr(self, node: nodes.AssignAttr) -> None:
        stripped = strip_to_name(node)
        if stripped is not None:
            self._add_var_event(stripped.name, stripped, VarEventType.MODIFY)

        return self.visit_many(node.get_children())

    def visit_delattr(self, node: nodes.DelAttr) -> None:
        stripped = strip_to_name(node)
        if stripped is None:
            return
        self._add_var_event(stripped.name, stripped, VarEventType.MODIFY)
