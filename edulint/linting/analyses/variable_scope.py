from typing import Dict, List, TypeVar, Union, Optional, Iterator

from astroid import nodes

from edulint.linting.checkers.utils import BaseVisitor, is_builtin


ScopeNode = Union[nodes.Module, nodes.FunctionDef, nodes.ClassDef, nodes.Lambda, nodes.GeneratorExp]
VarName = str

T = TypeVar("T")


def in_new_scope(func):
    def inner(self, *args, **kwargs):
        self.stack.append({})
        result = func(self, *args, **kwargs)
        self.stack.pop()
        return result

    return inner


class UnknowableLocalsException(Exception):
    pass


class ScopeListener(BaseVisitor[T]):
    def __init__(self):
        self.stack: List[Dict[VarName, ScopeNode]] = []
        super().__init__()

    def _get_var_scope_index(self, name: VarName) -> Optional[int]:
        for i, scope in enumerate(reversed(self.stack), 1):
            if name in scope:
                return -i
        return None

    def _get_var_scope(self, name: VarName) -> Optional[Dict[str, nodes.NodeNG]]:
        scope_index = self._get_var_scope_index(name)
        if scope_index is None:
            return None
        return self.stack[scope_index][name]

    def _init_var_in_scope(self, name: VarName, scope_node: nodes.NodeNG, offset: int = 0) -> None:
        if name not in self.stack[-1 + offset]:
            self.stack[-1 + offset][name] = scope_node.scope()

    def _del_var_from_scope(self, name: VarName, _node: nodes.NodeNG):
        scope_index = self._get_var_scope_index(name)
        if scope_index is None:
            return

        self.stack[scope_index].pop(name)

    @in_new_scope
    def visit_module(self, node: nodes.Module) -> T:
        return self.visit_many(node.get_children())

    @in_new_scope
    def visit_functiondef(self, node: nodes.FunctionDef) -> T:
        self._init_var_in_scope(node.name, node, offset=-1)

        for arg in node.argnames():
            self._init_var_in_scope(arg, node.args)

        return self.visit_many(node.body)

    @in_new_scope
    def visit_classdef(self, node: nodes.ClassDef) -> T:
        self._init_var_in_scope(node.name, node, offset=-1)

        return self.visit_many(node.get_children())

    @in_new_scope
    def visit_lambda(self, node: nodes.Lambda) -> T:
        for arg in node.argnames():
            self._init_var_in_scope(arg, node.args)

        return self.visit(node.body)

    @in_new_scope
    def visit_generatorexp(self, node: nodes.GeneratorExp) -> T:
        return self.visit_many(node.get_children())

    def visit_global(self, node: nodes.Global) -> T:
        for name in node.names:
            self.stack[-1][name] = node.root().scope()

        return self.default

    def visit_nonlocal(self, node: nodes.Nonlocal) -> T:
        for name in node.names:
            self.stack[-1][name] = node.scope().parent.scope()

        return self.default

    def _visit_assigned_to(self, node: nodes.NodeNG) -> None:
        if isinstance(node, nodes.AssignName):
            self._init_var_in_scope(node.name, node)

    def _names_from_tuple(self, targets: List[nodes.NodeNG]) -> Iterator[nodes.NodeNG]:
        for target in targets:
            if not isinstance(target, nodes.Tuple):
                yield target
            else:
                yield from self._names_from_tuple(target.elts)

    def visit_assignname(self, node: nodes.AssignName) -> T:
        self._visit_assigned_to(node)
        return self.default

    def visit_assign(self, node: nodes.Assign) -> T:
        for target in self._names_from_tuple(node.targets):
            self._visit_assigned_to(target)

        return self.visit(node.value)

    def visit_augassign(self, node: nodes.AugAssign) -> T:
        self._visit_assigned_to(node.target)
        return self.visit(node.value)

    def visit_annassign(self, node: nodes.AnnAssign) -> T:
        self._visit_assigned_to(node.target)
        if node.value is not None:
            return self.visit(node.value)
        return self.default

    def visit_delname(self, node: nodes.DelName) -> T:
        self._del_var_from_scope(node.name, node)
        return self.default

    def visit_import(self, node: nodes.Import) -> T:
        for module, alias in node.names:
            name = module if alias is None else alias
            self._init_var_in_scope(name, node)
        return self.default

    def visit_importfrom(self, node: nodes.ImportFrom) -> T:
        return self.visit_import(node)

    def visit_call(self, node: nodes.Call) -> T:
        if node.func.as_string() in ("locals", "globals") and is_builtin(node.func):
            raise UnknowableLocalsException(
                f"call to {node.func.as_string()}, unable to determine variable scopes"
            )
        return self.visit_many(node.get_children())

    def visit_for(self, node: nodes.For) -> T:
        return self.visit_many(node.get_children())
