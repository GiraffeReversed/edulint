from collections import defaultdict
import re
from typing import Dict, List, Union, Optional, Iterator, Tuple, Set

from astroid import nodes

from edulint.linting.analyses.cfg.utils import get_cfg_loc
from edulint.linting.checkers.utils import BaseVisitor, is_builtin
from edulint.linting.analyses.var_events import (
    VarEventType,
    VarName,
    Variable,
    VarEvent,
    strip_to_name,
    ScopeNode,
)


class VarEventsAnalysis:
    @staticmethod
    def collect(node: nodes.NodeNG):
        listener = VarEventListener()
        listener.visit(node)
        return (
            list(listener.variables),
            listener.function_defs,
            listener.call_graph,
            listener.outside_scope_events,
        )


def in_new_scope(func):
    def inner(self, *args, **kwargs):
        self.stack.append({})
        result = func(self, *args, **kwargs)
        self.stack.pop()
        return result

    return inner


class UnknowableLocalsException(Exception):
    pass


class VarEventListener(BaseVisitor[None]):
    NON_PURE_METHODS = re.compile(
        r"append|clear|extend|insert|pop|remove|reverse|sort|add|.*update|write"
    )

    def __init__(self):
        self.stack: List[Dict[VarName, Tuple[nodes.NodeNG, ScopeNode]]] = []
        self.variables: Set[Variable] = set()
        self.function_defs: List[nodes.FunctionDef] = []
        self.call_graph: Dict[ScopeNode, Set[ScopeNode]] = defaultdict(set)  # caller, calees
        self.outside_scope_events: Dict[ScopeNode, List[VarEvent]] = defaultdict(list)
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
        name_scope = self._get_var_node_scope(name)
        # assert scope is not None or VarEventListener.may_be_unscoped(
        #     name, name_node, loc.node
        # ), f"but {name_node.as_string()}, {loc.node.as_string()}"
        if name_scope is None:
            return

        init_name_node, scope = name_scope
        var = Variable(name, scope)
        event = VarEvent(var, name_node, action)
        loc.var_events.add(var, event)

        self.variables.add(var)

        if isinstance(name_node.parent, nodes.Call) and name_node == name_node.parent.func:
            self.call_graph[name_node.scope()].add(init_name_node)

        read_scope = (
            name_node.scope()
            if not isinstance(name_node, nodes.FunctionDef)
            else name_node.parent.scope()
        )
        while scope != read_scope:
            self.outside_scope_events[read_scope].append(event)
            read_scope = read_scope.parent

    def _get_var_scope_index(self, name: VarName) -> Optional[int]:
        for i, name_scope in enumerate(reversed(self.stack), 1):
            if name in name_scope:
                return -i
        return None

    def _get_var_node_scope(self, name: VarName) -> Optional[Tuple[nodes.NodeNG, ScopeNode]]:
        scope_index = self._get_var_scope_index(name)
        if scope_index is None:
            return None
        return self.stack[scope_index][name]

    def _init_var_in_scope(self, name: VarName, name_node: nodes.NodeNG) -> None:
        was_defined = name in self.stack[-1]
        if name not in self.stack[-1]:
            scope = (
                name_node.scope()
                if not isinstance(
                    name_node, (nodes.FunctionDef, nodes.AsyncFunctionDef, nodes.ClassDef)
                )
                else name_node.parent.scope()
            )
            self.stack[-1][name] = (name_node, scope)
        self._add_var_event(
            name, name_node, VarEventType.ASSIGN if not was_defined else VarEventType.REASSIGN
        )

    def _del_var_from_scope(self, name: VarName, node: nodes.NodeNG):
        self._add_var_event(name, node, VarEventType.DELETE)
        scope_index = self._get_var_scope_index(name)
        if scope_index is None:
            return

        self.stack[scope_index].pop(name)

    def statements_before_definitions(
        self, node: Union[nodes.Module, nodes.FunctionDef, nodes.AsyncFunctionDef]
    ):
        sooner = []
        later = []
        for child in node.body:
            if not isinstance(child, (nodes.FunctionDef, nodes.AsyncFunctionDef, nodes.ClassDef)):
                sooner.append(child)
            else:
                self._init_var_in_scope(child.name, child)
                later.append(child)
        return sooner + later

    @in_new_scope
    def visit_module(self, node: nodes.Module):
        return self.visit_many(self.statements_before_definitions(node))

    @in_new_scope
    def visit_functiondef(self, node: nodes.FunctionDef):
        self.function_defs.append(node)

        # args
        for ann in node.args.annotations:
            if ann is not None:
                self.visit(ann)

        for arg in node.args.arguments:
            self._init_var_in_scope(arg.name, arg)

        for default in node.args.defaults:
            self.visit(default)

        # posonly
        for ann in node.args.posonlyargs_annotations:
            if ann is not None:
                self.visit(ann)

        for arg in node.args.posonlyargs:
            self._init_var_in_scope(arg.name, arg)

        # kwonly
        for ann in node.args.kwonlyargs_annotations:
            if ann is not None:
                self.visit(ann)

        for arg in node.args.kwonlyargs:
            self._init_var_in_scope(arg.name, arg)

        # vararg
        if node.args.varargannotation is not None:
            self.visit(node.args.varargannotation)

        if node.args.vararg_node is not None:
            self._init_var_in_scope(node.args.vararg_node.name, node.args.vararg_node)

        # kwarg
        if node.args.kwargannotation is not None:
            self.visit(node.args.kwargannotation)

        if node.args.kwarg_node is not None:
            self._init_var_in_scope(node.args.kwarg_node.name, node.args.kwarg_node)

        return self.visit_many(self.statements_before_definitions(node))

    def visit_asyncfunctiondef(self, node: nodes.AsyncFunctionDef):
        self.visit_functiondef(node)

    @in_new_scope
    def visit_classdef(self, node: nodes.ClassDef):
        return self.visit_many(self.statements_before_definitions(node))

    @in_new_scope
    def visit_lambda(self, node: nodes.Lambda):
        for arg in node.args.arguments:
            self._init_var_in_scope(arg.name, arg)

        return self.visit(node.body)

    def _visit_generator(
        self, node: Union[nodes.GeneratorExp, nodes.ListComp, nodes.DictComp, nodes.SetComp]
    ):
        self.visit_many(node.generators)
        if isinstance(node, nodes.DictComp):
            self.visit(node.key)
            return self.visit(node.value)
        return self.visit(node.elt)

    @in_new_scope
    def visit_generatorexp(self, node: nodes.GeneratorExp):
        return self._visit_generator(node)

    @in_new_scope
    def visit_listcomp(self, node: nodes.ListComp):
        return self._visit_generator(node)

    @in_new_scope
    def visit_dictcomp(self, node: nodes.DictComp):
        return self._visit_generator(node)

    @in_new_scope
    def visit_setcomp(self, node: nodes.SetComp):
        return self._visit_generator(node)

    def visit_global(self, node: nodes.Global):
        for name in node.names:
            self.stack[-1][name] = (node, node.root().scope())

        return self.default

    def visit_nonlocal(self, node: nodes.Nonlocal):
        for name in node.names:
            self.stack[-1][name] = (node, node.scope().parent.scope())

        return self.default

    def _visit_assigned_to(self, node: nodes.NodeNG) -> None:
        if isinstance(node, nodes.AssignName):
            self._init_var_in_scope(node.name, node)
        self.visit_many(node.get_children())

        stripped = strip_to_name(node)
        if stripped is None:
            return

        if isinstance(node, (nodes.AssignAttr, nodes.Subscript)):
            self._add_var_event(stripped.name, stripped, VarEventType.MODIFY)

    def _names_from_tuple(self, targets: List[nodes.NodeNG]) -> Iterator[nodes.NodeNG]:
        for target in targets:
            if not isinstance(target, nodes.Tuple):
                yield target
            else:
                yield from self._names_from_tuple(target.elts)

    def visit_assignname(self, node: nodes.AssignName):
        self._visit_assigned_to(node)
        return self.default

    def visit_assign(self, node: nodes.Assign):
        self.visit(node.value)

        for target in self._names_from_tuple(node.targets):
            self._visit_assigned_to(target)

        return self.default

    def visit_augassign(self, node: nodes.AugAssign):
        stripped = strip_to_name(node.target)
        if stripped is not None:
            self._add_var_event(stripped.name, stripped, VarEventType.READ)

        self.visit(node.value)
        self._visit_assigned_to(node.target)

    def visit_annassign(self, node: nodes.AnnAssign):
        self.visit(node.annotation)
        if node.value is not None:
            self.visit(node.value)
        self._visit_assigned_to(node.target)
        return self.default

    def visit_delname(self, node: nodes.DelName):
        self._del_var_from_scope(node.name, node)
        return self.default

    def visit_import(self, node: nodes.Import):
        for module, alias in node.names:
            name = module if alias is None else alias
            self._init_var_in_scope(name, node)
        return self.default

    def visit_importfrom(self, node: nodes.ImportFrom):
        return self.visit_import(node)

    def visit_call(self, node: nodes.Call):
        if node.func.as_string() in ("locals", "globals") and is_builtin(node.func):
            raise UnknowableLocalsException(
                f"call to {node.func.as_string()} on line {node.fromlineno} in {node.root().file}; "
                " unable to determine variable scopes. This may disable some detectors."
            )
        return self.visit_many(node.get_children())

    def visit_for(self, node: nodes.For):
        return self.visit_many(node.get_children())

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
