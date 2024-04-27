from collections import namedtuple
from typing import Union, Optional
from enum import Enum, auto
import re

from astroid import nodes

from edulint.linting.analyses.cfg.graph import CFGLoc
from edulint.linting.analyses.cfg.utils import get_cfg_loc
from edulint.linting.analyses.variable_scope import ScopeListener, VarName
from edulint.linting.checkers.utils import is_builtin


class VarEventType(Enum):
    ASSIGN = auto()
    REASSIGN = auto()
    MODIFY = auto()
    READ = auto()
    DELETE = auto()


ScopeNode = Union[nodes.Module, nodes.FunctionDef, nodes.ClassDef, nodes.Lambda, nodes.GeneratorExp]

VarEvent = namedtuple("VarEvent", ["varname", "scope", "event"])


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

    def _add_var_event(self, name: VarName, loc: CFGLoc, action: VarEventType):
        scope = self._get_var_scope(name)
        assert (
            scope is not None
            or name.startswith("__")
            or (isinstance(loc.node, nodes.Call) and is_builtin(loc.node.func, name))
            or (
                isinstance(loc.node, (nodes.Expr, nodes.Assign))
                and isinstance(loc.node.value, nodes.Call)
                and is_builtin(loc.node.value.func, name)
            )
            or (
                isinstance(loc.node, nodes.ExceptHandler)
                and loc.node.type is not None
                and is_builtin(loc.node.type, name)
            )
        )
        loc.var_events.append(VarEvent(name, scope, action))

    # @override
    def _init_var_in_scope(self, name: VarName, scope_node: nodes.NodeNG, offset: int = 0) -> None:
        was_defined = name in self.stack[-1 + offset]
        super()._init_var_in_scope(name, scope_node, offset)
        self._add_var_event(
            name,
            get_cfg_loc(scope_node),
            VarEventType.ASSIGN if not was_defined else VarEventType.REASSIGN,
        )

    # @override
    def _del_var_from_scope(self, name: VarName, node: nodes.NodeNG):
        self._add_var_event(name, get_cfg_loc(node), VarEventType.DELETE)
        super()._del_var_from_scope(name, node)

    @staticmethod
    def _strip(node: nodes.NodeNG) -> Optional[Union[nodes.Name, nodes.AssignName, nodes.DelName]]:
        while True:
            if isinstance(node, nodes.Subscript):
                node = node.value
            elif type(node) in (nodes.Attribute, nodes.AssignAttr, nodes.DelAttr):
                node = node.expr
            else:
                break

        return node if isinstance(node, (nodes.Name, nodes.AssignName, nodes.DelName)) else None

    # @override
    def _visit_assigned_to(self, node: nodes.NodeNG) -> None:
        super()._visit_assigned_to(node)

        stripped = self._strip(node)
        if stripped is None:
            return

        if isinstance(node, (nodes.AssignAttr, nodes.Subscript)):
            self._add_var_event(stripped.name, get_cfg_loc(node), VarEventType.MODIFY)

    # @override
    def visit_augassign(self, node: nodes.AugAssign) -> None:
        self._add_var_event(node.target.name, get_cfg_loc(node), VarEventType.READ)
        super().visit_augassign(node)

    def visit_name(self, node: nodes.Name) -> None:
        self._add_var_event(node.name, get_cfg_loc(node), VarEventType.READ)

    def visit_attribute(self, node: nodes.Attribute) -> None:
        stripped = self._strip(node)
        if (
            isinstance(node.parent, nodes.Call)
            and VarEventListener.NON_PURE_METHODS.match(node.attrname)
            and stripped is not None
        ):
            self._add_var_event(stripped.name, get_cfg_loc(node), VarEventType.MODIFY)

        return self.visit_many(node.get_children())

    def visit_delattr(self, node: nodes.DelAttr) -> None:
        stripped = self._strip(node)
        if stripped is None:
            return
        self._add_var_event(stripped.name, get_cfg_loc(node), VarEventType.MODIFY)
