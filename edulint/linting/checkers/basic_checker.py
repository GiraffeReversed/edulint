from astroid import nodes, Context  # type: ignore
from typing import TYPE_CHECKING, Optional, List, Union, Tuple
from enum import Enum, auto
from functools import reduce

from pylint.checkers import BaseChecker  # type: ignore
from pylint.checkers.utils import only_required_for_messages

if TYPE_CHECKING:
    from pylint.lint import PyLinter  # type: ignore

from edulint.linting.checkers.utils import (
    get_name,
    is_builtin,
    get_range_params,
    get_statements_count,
)
from edulint.linting.checkers.modified_listener import ModifiedListener


class UsesIndex(Enum):
    OUTSIDE_SUBSCRIPT = auto()
    INSIDE_SUBSCRIPT = auto()
    NEVER = auto()

    @classmethod
    def combine(cls, lt: "UsesIndex", rt: "UsesIndex") -> "UsesIndex":
        if lt == cls.INSIDE_SUBSCRIPT or rt == cls.INSIDE_SUBSCRIPT:
            return cls.INSIDE_SUBSCRIPT
        if lt == cls.OUTSIDE_SUBSCRIPT or rt == cls.OUTSIDE_SUBSCRIPT:
            return cls.OUTSIDE_SUBSCRIPT
        return cls.NEVER


class ImproveForLoop(BaseChecker):  # type: ignore
    name = "improve-for-loop"
    msgs = {
        "R6101": (
            'Iterate directly: "for var in %s" (with appropriate name for "var")',
            "use-foreach",
            "Emitted when a for-range loop is used while a for-each loop would suffice.",
        ),
        "R6102": (
            'Iterate using enumerate: "for %s, var in enumerate(%s)" (with appropriate name for "var")',
            "use-enumerate",
            "Emitted when a for-range loop is used with the element at each index is accessed as well.",
        ),
    }

    def __init__(self, linter: Optional["PyLinter"] = None) -> None:
        super().__init__(linter)

    class StructureIndexedVisitor(ModifiedListener[Tuple[bool, bool]]):
        default = (False, False)

        @staticmethod
        def combine(results: List[Tuple[bool, bool]]) -> Tuple[bool, bool]:
            return any(loaded for loaded, _stored in results), any(
                stored for _loaded, stored in results
            )

        def __init__(self, structure: Union[nodes.Name, nodes.Attribute], index: nodes.Name):
            super().__init__([structure, index])
            self.structure = structure
            self.index = index

        def visit_subscript(self, subscript: nodes.Subscript) -> Tuple[bool, bool]:
            sub_loaded, sub_stored = self.visit_many(subscript.get_children())

            if self.was_reassigned(self.structure, allow_definition=False) or self.was_reassigned(
                self.index, allow_definition=False
            ):
                return False, False

            used = (
                subscript.value.as_string() == self.structure.as_string()
                and isinstance(subscript.slice, nodes.Name)
                and subscript.slice.as_string() == self.index.as_string()
            )

            if subscript.ctx == Context.Store:
                return sub_loaded, sub_stored or used

            if subscript.ctx == Context.Load:
                return sub_loaded or used, sub_stored

            assert subscript.ctx == Context.Del
            return sub_loaded, sub_stored or used

    class StructureIndexedByAnyOtherVisitor(ModifiedListener[bool]):
        default = False

        @staticmethod
        def combine(results: List[bool]) -> bool:
            return any(results)

        def __init__(self, structure: Union[nodes.Name, nodes.Attribute], index: nodes.Name):
            super().__init__([structure, index])
            self.structure = structure
            self.index = index

        def visit_subscript(self, subscript: nodes.Subscript) -> bool:
            sub_indexed = self.visit_many(subscript.get_children())

            if self.was_reassigned(self.structure, allow_definition=False) or self.was_reassigned(
                self.index, allow_definition=False
            ):
                return True

            return sub_indexed or (
                subscript.value.as_string() == self.structure.as_string()
                and (
                    not isinstance(subscript.slice, nodes.Name)
                    or subscript.slice.as_string() != self.index.as_string()
                )
            )

    class IndexUsedVisitor(ModifiedListener[UsesIndex]):
        default = UsesIndex.NEVER

        @staticmethod
        def combine(results: List[UsesIndex]) -> UsesIndex:
            return reduce(UsesIndex.combine, results, UsesIndex.NEVER)

        def __init__(self, structure: Union[nodes.Name, nodes.Attribute], index: nodes.Name):
            super().__init__([structure, index])
            self.structure = structure
            self.index = index

        def visit_name(self, name: nodes.Name) -> UsesIndex:
            if name.name != self.index.name:
                return UsesIndex.NEVER

            parent = name.parent
            if (
                isinstance(parent, nodes.Subscript)
                and parent.value.as_string() != self.structure.as_string()
            ):
                return UsesIndex.INSIDE_SUBSCRIPT

            if (
                not isinstance(name.parent, nodes.Subscript)
                or not isinstance(self.structure, type(name.parent.value))
                or self.was_reassigned(name, allow_definition=False)
            ):
                return UsesIndex.OUTSIDE_SUBSCRIPT

            subscript = name.parent
            if not (
                (
                    isinstance(subscript.value, nodes.Name)
                    and subscript.value.name == self.structure.name
                )
                or (
                    isinstance(subscript.value, nodes.Attribute)
                    and subscript.value.attrname == self.structure.attrname
                )
            ):
                return UsesIndex.OUTSIDE_SUBSCRIPT

            if isinstance(subscript.parent, nodes.Assign) and subscript in subscript.parent.targets:
                return UsesIndex.OUTSIDE_SUBSCRIPT

            return UsesIndex.NEVER

    def visit_for(self, node: nodes.For) -> None:
        range_params = get_range_params(node.iter)
        if range_params is None:
            return

        start, stop, step = range_params
        if (
            not isinstance(start, nodes.Const)
            or start.value != 0
            or not isinstance(stop, nodes.Call)
            or not is_builtin(stop.func, "len")
            or len(stop.args) != 1
            or not isinstance(step, nodes.Const)
            or step.value != 1
        ):
            return

        structure = stop.args[0]
        index = node.target
        if not isinstance(structure, nodes.Name) and not isinstance(structure, nodes.Attribute):
            return

        loaded, stored = self.StructureIndexedVisitor(structure, node.target).visit_many(node.body)
        if not loaded:
            return

        structure_name = get_name(structure)
        uses_index = self.IndexUsedVisitor(structure, node.target).visit_many(node.body)

        if uses_index == UsesIndex.INSIDE_SUBSCRIPT or self.StructureIndexedByAnyOtherVisitor(
            structure, index
        ).visit_many(node.body):
            return
        elif stored or uses_index == UsesIndex.OUTSIDE_SUBSCRIPT:
            self.add_message("use-enumerate", args=(index.name, structure_name), node=node)
        else:
            assert uses_index == UsesIndex.NEVER
            self.add_message("use-foreach", args=structure_name, node=node)


class NoGlobalVars(BaseChecker):
    name = "no-global-variables"
    msgs = {
        "R6401": (
            "Do not use global variables; you use %s, modifying it for example at line %i.",
            "no-global-vars",
            "Emitted when the code uses global variables.",
        ),
    }

    def __init__(self, linter: "PyLinter"):
        super().__init__(linter)
        self.to_check = {}

    def visit_assignname(self, node: nodes.AssignName) -> None:
        frame = node.frame()
        if not isinstance(frame, nodes.Module):
            return

        if frame not in self.to_check:
            self.to_check[frame] = {}

        if node.name in self.to_check[frame].keys():
            return

        self.to_check[frame][node.name] = node

    def close(self) -> None:
        for frame, vars_ in self.to_check.items():
            listener = ModifiedListener(list(vars_.values()))
            listener.visit(frame)
            for node in vars_.values():
                if listener.was_modified(node, allow_definition=True):
                    nonglobal_modifiers = [
                        n for n in listener.get_all_modifiers(node) if n.scope() != node.scope()
                    ]
                    if nonglobal_modifiers:
                        self.add_message(
                            "no-global-vars",
                            node=node,
                            args=(node.name, nonglobal_modifiers[0].lineno),
                        )


class LongCodeChecker(BaseChecker):
    name = "long-code"
    msgs = {
        "R6701": (
            "Too much code outside of functions or classes (%d which is over %d statements).",
            "long-script",
            "Emitted when there are too many lines of code on the top level that are not import or function or class "
            "definition.",
        ),
        "R6702": (
            "Function '%s' is too long (%d which is over %d statements).",
            "long-function",
            "Emitted when there are too many statements inside a function definition.",
        ),
    }

    @only_required_for_messages("long-script")
    def visit_module(self, node: nodes.Module):
        MAX_SCRIPT = 20

        count = get_statements_count(node, include_defs=False, include_name_main=False)
        if count > MAX_SCRIPT:
            self.add_message("long-script", node=node, args=(count, MAX_SCRIPT))

    @only_required_for_messages("long-function")
    def visit_functiondef(self, node: nodes.FunctionDef):
        MAX_FUNC = 20

        count = get_statements_count(node.body, include_defs=False, include_name_main=False)
        if count > MAX_FUNC:
            self.add_message("long-function", node=node, args=(node.name, count, MAX_FUNC))


def register(linter: "PyLinter") -> None:
    """This required method auto registers the checker during initialization.
    :param linter: The linter to register the checker to.
    """
    linter.register_checker(ImproveForLoop(linter))
    linter.register_checker(NoGlobalVars(linter))
    linter.register_checker(LongCodeChecker(linter))
