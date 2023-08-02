from astroid import nodes  # type: ignore
from typing import Optional, List, Union, TypeVar, Iterator, Dict
import re

from edulint.linting.checkers.utils import BaseVisitor, Named, get_name


T = TypeVar("T")


class ModifiedListener(BaseVisitor[T]):
    NON_PURE_METHODS = re.compile(
        r"append|clear|extend|insert|pop|remove|reverse|sort|add|.*update|write"
    )

    def __init__(self, watched: List[Named]):
        self.watched = watched
        self.modified: Dict[str, List[nodes.NodeNG]] = {get_name(var): [] for var in watched}
        self.stack = [{get_name(var): var.scope() for var in watched}]
        super().__init__()

    def _init_var_in_scope(self, node: nodes.NodeNG) -> None:
        self.stack[-1][get_name(node)] = node.scope()

    def visit_functiondef(self, node: nodes.FunctionDef) -> T:
        self.stack.append({})
        for arg in node.args.args:
            self._init_var_in_scope(arg)

        result = self.visit_many(node.get_children())

        self.stack.pop()
        return result

    def visit_global(self, node: nodes.Global) -> T:
        for name in node.names:
            self.stack[-1][name] = node.root().scope()

        return self.default

    def visit_nonlocal(self, node: nodes.Nonlocal) -> T:
        for name in node.names:
            self.stack[-1][name] = node.scope().parent.scope()

        return self.default

    def was_modified(self, node: nodes.NodeNG, allow_definition: bool) -> bool:
        return len(self.get_all_modifiers(node)) > (1 if allow_definition else 0)

    @staticmethod
    def _reassigns(node: nodes.NodeNG) -> bool:
        return type(node) in (nodes.AssignName, nodes.AssignAttr, nodes.DelName, nodes.DelAttr)

    def was_reassigned(self, node: nodes.NodeNG, allow_definition: bool) -> bool:
        return sum(self._reassigns(mod) for mod in self.get_all_modifiers(node)) > (
            1 if allow_definition else 0
        )

    def get_all_modifiers(self, node: nodes.NodeNG) -> List[nodes.NodeNG]:
        return self.modified[get_name(node)]

    def get_sure_modifiers(self, node: nodes.NodeNG) -> List[nodes.NodeNG]:
        result = []
        for modifier in self.get_all_modifiers(node):
            if ModifiedListener._reassigns(modifier):
                break
            result.append(modifier)
        return result

    @staticmethod
    def _strip(node: nodes.NodeNG) -> Optional[Union[nodes.Name, nodes.AssignName]]:
        while True:
            if isinstance(node, nodes.Subscript):
                node = node.value
            elif type(node) in (nodes.Attribute, nodes.AssignAttr, nodes.DelAttr):
                node = node.expr
            else:
                break

        return node if type(node) in (nodes.Name, nodes.AssignName, nodes.DelName) else None

    def _get_var_scope(self, var: str) -> Optional[Dict[str, nodes.NodeNG]]:
        for scope in reversed(self.stack):
            if var in scope:
                return scope
        return None

    def _is_same_var(self, var: Named, node: Named) -> bool:
        varname = get_name(var)
        scope = self._get_var_scope(varname)
        return varname == get_name(node) and scope is not None and scope[varname] == var.scope()

    def _visit_assigned_to(self, node: nodes.NodeNG) -> None:
        stripped = self._strip(node)
        if stripped is None:
            return

        if isinstance(node, nodes.AssignName) and get_name(stripped) not in self.stack[-1]:
            self._init_var_in_scope(stripped)

        for var in self.watched:
            if self._is_same_var(var, stripped):
                self.modified[get_name(var)].append(node)

    def _names_from_tuple(self, targets: List[nodes.NodeNG]) -> Iterator[nodes.NodeNG]:
        for target in targets:
            if not isinstance(target, nodes.Tuple):
                yield target
            else:
                yield from self._names_from_tuple(target.elts)

    def visit_assign(self, assign: nodes.Assign) -> T:
        for target in self._names_from_tuple(assign.targets):
            self._visit_assigned_to(target)

        return self.visit_many(assign.get_children())

    def visit_augassign(self, node: nodes.AugAssign) -> T:
        self._visit_assigned_to(node.target)
        return self.visit_many(node.get_children())

    def visit_annassign(self, node: nodes.AnnAssign) -> T:
        self._visit_assigned_to(node.target)
        return self.visit_many(node.get_children())

    def visit_attribute(self, node: nodes.Attribute) -> T:
        if isinstance(node.parent, nodes.Call) and ModifiedListener.NON_PURE_METHODS.match(
            node.attrname
        ):
            stripped = self._strip(node)
            if stripped is None:
                return self.visit_many(node.get_children())

            for var in self.watched:
                if self._is_same_var(var, stripped):
                    self.modified[get_name(var)].append(node.parent)

        return self.visit_many(node.get_children())

    def visit_del(self, node: nodes.Delete) -> T:
        for target in node.targets:
            if isinstance(target, nodes.DelName):
                scope = self._get_var_scope(target.name)
                if scope is not None:
                    scope.pop(target.name)

            stripped = self._strip(target)

            for var in self.watched:
                if self._is_same_var(var, stripped):
                    self.modified[get_name(var)].append(
                        target if type(target) in (nodes.DelName, nodes.DelAttr) else node
                    )

        return self.visit_many(node.get_children())

    def visit_for(self, node: nodes.For) -> T:
        self._visit_assigned_to(node.target)
        return self.visit_many(node.get_children())
