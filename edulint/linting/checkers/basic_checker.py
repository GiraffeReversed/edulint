from astroid import nodes  # type: ignore
from typing import TYPE_CHECKING, Optional, List, Union, TypeVar

from pylint.checkers import BaseChecker  # type: ignore

if TYPE_CHECKING:
    from pylint.lint import PyLinter  # type: ignore

from edulint.linting.checkers.utils import \
    BaseVisitor, Named, get_name, get_assigned, is_any_assign, is_named, is_builtin


class AugmentAssignments(BaseChecker):  # type: ignore

    name = "augment-assignments"
    msgs = {
        "R6001": (
            "Use augmenting assignment: \"%s %s= %s\"",
            "use-augmenting-assignment",
            "Emitted when an assignment can be simplified by using its augmented version.",
        ),
    }

    def add_augmenting_message(self, bin_op: nodes.BinOp, param: nodes.BinOp, name: str) -> None:
        self.add_message("use-augmenting-assignment", node=bin_op, args=(name, bin_op.op, param.as_string()))

    def visit_binop(self, bin_op: nodes.BinOp) -> None:
        if not is_any_assign(bin_op.parent):
            return

        targets = get_assigned(bin_op.parent)
        if len(targets) != 1:
            return

        name = get_name(targets[0])
        if is_named(bin_op.left) and name == get_name(bin_op.left):
            self.add_augmenting_message(bin_op, bin_op.right, name)
        if bin_op.op in "+*|&" and is_named(bin_op.right) and name == get_name(bin_op.right):
            self.add_augmenting_message(bin_op, bin_op.left, name)


T = TypeVar("T")


class ImproveForLoop(BaseChecker):  # type: ignore

    name = "improve-for-loop"
    msgs = {
        "R6101": (
            "Iterate directly: \"for var in %s\" (with appropriate name for \"var\")",
            "use-foreach",
            "Emitted when a for-range loop is used while a for-each loop would suffice.",
        ),
        "R6102": (
            "Iterate using enumerate: \"for %s, var in enumerate(%s)\" (with appropriate name for \"var\")",
            "use-enumerate",
            "Emitted when a for-range loop is used with the element at each index is accessed as well.",
        ),
    }

    def __init__(self, linter: Optional["PyLinter"] = None) -> None:
        super().__init__(linter)

    def _is_for_range(self, node: nodes.For) -> bool:
        return isinstance(node.iter, nodes.Call) \
            and is_builtin(node.iter.func, "range") \
            and (len(node.iter.args) == 1
                 or (len(node.iter.args) == 2
                     and isinstance(node.iter.args[0], nodes.Const)
                     and node.iter.args[0].value == 0)) \
            and is_builtin(node.iter.args[0].func, "len") \
            and len(node.iter.args[0].args) == 1

    def _get_structure(self, node: nodes.For) -> nodes.NodeNG:
        return node.iter.args[0].args[0]

    class ModifiedListener(BaseVisitor[T]):

        def __init__(self, watched: List[Named]):
            self.watched = watched
            self.modified = {get_name(var): False for var in watched}
            super().__init__()

        def was_modified(self, node: nodes.NodeNG) -> bool:
            return self.modified[get_name(node)]

        @staticmethod
        def _is_assigned_to(node: Named) -> bool:
            return node in get_assigned(node.parent)

        @staticmethod
        def _is_same_var(var: Named, node: Named) -> bool:
            return var.scope() == node.scope() and isinstance(var, type(node)) and get_name(var) == get_name(node)

        def _visit_assigned_to(self, node: Named) -> T:
            if not self._is_assigned_to(node):
                return self.default

            for var in self.watched:
                if self._is_same_var(var, node):
                    self.modified[get_name(var)] = True

            return self.default

        def visit_name(self, name: nodes.Name) -> T:
            return self._visit_assigned_to(name)

        def visit_attribute(self, attribute: nodes.Attribute) -> T:
            return self._visit_assigned_to(attribute)

        def visit_assignname(self, assign: nodes.AssignName) -> T:
            return self._visit_assigned_to(assign)

    class StructureIndexedVisitor(ModifiedListener[bool]):
        default = False

        @staticmethod
        def combine(results: List[bool]) -> bool:
            return any(results)

        def __init__(self, structure: Union[nodes.Name, nodes.Attribute], index: nodes.Name):
            self.structure = structure
            self.index = index
            super().__init__([structure, index])

        def visit_subscript(self, subscript: nodes.Subscript) -> bool:
            sub_result = self.visit_many(subscript.get_children())
            if sub_result:
                return sub_result

            parent = subscript.parent
            if self.was_modified(self.structure) or self.was_modified(self.index):
                return False
            if not isinstance(subscript.value, type(self.structure)) \
                    or (isinstance(parent, nodes.Assign) and subscript in parent.targets) \
                    or not isinstance(subscript.slice, nodes.Name):
                return sub_result

            return subscript.slice.name == self.index.name and (
                (isinstance(self.structure, nodes.Name) and self.structure.name == subscript.value.name)
                or (isinstance(self.structure, nodes.Attribute) and self.structure.attrname == subscript.value.attrname)
            )

    class IndexUsedVisitor(ModifiedListener[bool]):
        default = False

        @staticmethod
        def combine(results: List[bool]) -> bool:
            return any(results)

        def __init__(self, structure: Union[nodes.Name, nodes.Attribute], index: nodes.Name):
            self.structure = structure
            self.index = index
            super().__init__([structure, index])

        def visit_name(self, name: nodes.Name) -> bool:
            super().visit_name(name)
            if name.name != self.index.name:
                return False
            if not isinstance(name.parent, nodes.Subscript) \
                    or not isinstance(self.structure, type(name.parent.value)) \
                    or self.modified[get_name(name)]:
                return True

            subscript = name.parent
            if not ((isinstance(subscript.value, nodes.Name)
                    and subscript.value.name == self.structure.name)
                    or (isinstance(subscript.value, nodes.Attirbute)
                    and subscript.value.attrname == self.structure.attrname)):
                return True

            return isinstance(subscript.parent, nodes.Assign) and subscript in subscript.parent.targets

    def visit_for(self, node: nodes.For) -> None:
        if not self._is_for_range(node):
            return

        structure = self._get_structure(node)
        index = node.target
        if not isinstance(structure, nodes.Name) and not isinstance(structure, nodes.Attribute):
            return

        if self.StructureIndexedVisitor(structure, node.target).visit_many(node.body):
            structure_name = get_name(structure)
            if self.IndexUsedVisitor(structure, node.target).visit_many(node.body):
                self.add_message("use-enumerate", args=(index.name, structure_name), node=node)
            else:
                self.add_message("use-foreach", args=structure_name, node=node)


def register(linter: "PyLinter") -> None:
    """This required method auto registers the checker during initialization.
    :param linter: The linter to register the checker to.
    """
    linter.register_checker(AugmentAssignments(linter))
    linter.register_checker(ImproveForLoop(linter))
