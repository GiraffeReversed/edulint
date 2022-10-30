from astroid import nodes  # type: ignore
from typing import TYPE_CHECKING, Optional, List, Tuple, Union, TypeVar

from pylint.checkers import BaseChecker  # type: ignore

if TYPE_CHECKING:
    from pylint.lint import PyLinter  # type: ignore

from edulint.linting.checkers.utils import \
    BaseVisitor, Named, get_name, get_assigned_to, is_any_assign, is_named, is_builtin


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

        targets = get_assigned_to(bin_op.parent)
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
            return node in get_assigned_to(node.parent)

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


class SimplifiableIf(BaseChecker):  # type: ignore

    name = "simplifiable-if"
    msgs = {
        "R6201": (
            "The if statement can be replaced with 'return %s'",
            "simplifiable-if-return",
            "Emitted when returning a boolean value can be simplified.",
        ),
        "R6202": (
            "The if statement can be merged with the next to 'if %s:'",
            "simplifiable-if-merge",
            "Emitted when an if statement can be merged with the next using a logical operator"
        ),
        "R6203": (
            "The conditional assignment can be replace with '%s = %s'",
            "simplifiable-if-assignment",
            "Emitted when an assignment in an if statement can be simplified."
        ),
        "R6204": (
            "The if expression can be replaced with '%s'",
            "simplifiable-if-expr",
            "Emitted when an if expression can be omitted."
        ),
        "R6205": (
            "Use 'if %s: <else body>' instead of 'pass'",
            "simplifiable-if-pass",
            "Emitted when there is an if condition with a pass in the positive branch."
        )
    }

    def _is_bool(self, node: nodes.NodeNG) -> bool:
        return isinstance(node, nodes.Const) and node.pytype() == "builtins.bool"

    def _simplifiable_if_message(self, node: nodes.If, then: nodes.NodeNG, new_cond: str) -> None:
        if isinstance(node, nodes.IfExp):
            self.add_message("simplifiable-if-expr", node=node, args=(new_cond))
        elif isinstance(then, nodes.Return):
            self.add_message("simplifiable-if-return", node=node, args=(new_cond))
        else:
            self.add_message("simplifiable-if-assignment", node=node,
                             args=(get_name(get_assigned_to(then)[0]), new_cond))

    def _get_refactored(self, *args) -> str:
        result = []
        i = 0
        while i < len(args):
            arg = args[i]
            if isinstance(arg, str) and arg == "not":
                refactored = args[i + 1].as_string()
                if isinstance(args[i+1], nodes.BoolOp):
                    result.append(f"<negated ({refactored})>")
                else:
                    result.append(f"<negated {refactored}>")
                i += 2
            elif isinstance(arg, str) and arg in ("and", "or"):
                prev = args[i - 1]
                next_ = args[i + 1]
                if isinstance(prev, nodes.BoolOp) and prev.op != arg and (i - 2 < 0 or args[i - 2] != "not"):
                    result[-1] = f"({result[-1]})"
                result.append(arg)
                i += 1
                if isinstance(next_, nodes.BoolOp) and next_.op != arg:
                    result.append(f"({next_.as_string()})")
                    i += 1
            elif isinstance(arg, nodes.NodeNG):
                result.append(arg.as_string())
                i += 1

        return " ".join(result)

    def _names_assigned_to(self, node: nodes.NodeNG):
        return sorted([get_name(t) for t in get_assigned_to(node)])

    def _get_then_orelse(self, node: nodes.If) -> Optional[Tuple[nodes.NodeNG, nodes.NodeNG]]:
        if len(node.body) != 1 or len(node.orelse) > 1:
            return None

        then = node.body[0]

        if len(node.orelse) == 1:
            return then, node.orelse[0]

        after_if = node.next_sibling()
        if not isinstance(then, nodes.Return) or not isinstance(after_if, nodes.Return):
            return None

        return then, after_if

    def _refactored_cond_from_then_orelse(self, node: nodes.If, then_value: nodes.NodeNG, orelse_value: nodes.NodeNG) \
            -> Optional[str]:
        then_bool_value = then_value.value if self._is_bool(then_value) else None
        orelse_bool_value = orelse_value.value if self._is_bool(orelse_value) else None

        if then_bool_value is None and orelse_bool_value is None:
            return None

        if then_bool_value is not None and orelse_bool_value is not None:
            if then_bool_value and not orelse_bool_value:
                return self._get_refactored(node.test)
            if not then_bool_value and orelse_bool_value:
                return self._get_refactored("not", node.test)
            return None

        if then_bool_value is not None and then_bool_value:
            return self._get_refactored(node.test, "or", orelse_value)

        if then_bool_value is not None and not then_bool_value:
            return self._get_refactored("not", node.test, "and", orelse_value)

        if orelse_bool_value is not None and orelse_bool_value:
            return self._get_refactored("not", node.test, "or", then_value)

        if orelse_bool_value is not None and not orelse_bool_value:
            return self._get_refactored(node.test, "and", then_value)

        assert False, "unreachable"

    def _merge_nested(self, node: nodes.If) -> None:
        refactored = self._get_refactored(node.test, "and", node.body[0].test)
        self.add_message("simplifiable-if-merge", node=node, args=refactored)

    def _same_values(self, node1: nodes.NodeNG, node2: nodes.NodeNG) -> bool:
        return node1.as_string() == node2.as_string()

    def _mergeable(self, node1: nodes.NodeNG, node2: nodes.NodeNG) -> bool:
        return isinstance(node1, type(node2)) and (isinstance(node1, nodes.Return) or (
            is_any_assign(node1)
            and len(get_assigned_to(node1)) == 1
            and self._names_assigned_to(node1) == self._names_assigned_to(node2)
        ))

    def _merge_sequential(self, node: nodes.If) -> None:
        after_if = node.next_sibling()

        if isinstance(node.test, nodes.BoolOp) or isinstance(after_if.test, nodes.BoolOp) \
                or len(after_if.orelse) != 0 or len(node.body) != 1 or len(after_if.body) != 1:
            return

        body1 = node.body[0]
        body2 = after_if.body[0]
        if not isinstance(body1, type(body2)) \
                or not isinstance(body1, nodes.Return) \
                or not self._same_values(body1.value, body2.value):
            return

        refactored = self._get_refactored(node.test, "or", after_if.test)
        self.add_message("simplifiable-if-merge", node=node, args=(refactored))

    def _is_just_returning_if(self, node: Optional[nodes.NodeNG]) -> bool:
        return node is not None and isinstance(node, nodes.If) and isinstance(nodes.body[-1], nodes.Return)

    def visit_if(self, node: nodes.If) -> None:
        if len(node.orelse) == 0:
            if len(node.body) == 1 and isinstance(node.body[0], nodes.If) and len(node.body[0].orelse) == 0:
                self._merge_nested(node)
                return

            if node.next_sibling() is not None and isinstance(node.next_sibling(), nodes.If):
                self._merge_sequential(node)
                return

        if len(node.body) == 1 and isinstance(node.body[0], nodes.Pass) and len(node.orelse) > 0:
            self.add_message("simplifiable-if-pass", node=node, args=(self._get_refactored("not", node.test)))
            return

        then_orelse = self._get_then_orelse(node)

        if not then_orelse:
            return

        then, orelse = then_orelse
        if not self._mergeable(then, orelse):
            return

        refactored = self._refactored_cond_from_then_orelse(node, then.value, orelse.value)

        if refactored is not None and not self._is_just_returning_if(node.previous_sibling()):
            self._simplifiable_if_message(node, then, refactored)

    def visit_ifexp(self, node: nodes.IfExp) -> None:
        then, orelse = node.body, node.orelse
        assert then is not None and orelse is not None

        if (not isinstance(then, nodes.Const) and not isinstance(then, nodes.Name)) or \
                (not isinstance(orelse, nodes.Const) and not isinstance(orelse, nodes.Name)):
            return

        refactored = self._refactored_cond_from_then_orelse(node, then, orelse)
        if refactored is not None:
            self._simplifiable_if_message(node, then, refactored)


def register(linter: "PyLinter") -> None:
    """This required method auto registers the checker during initialization.
    :param linter: The linter to register the checker to.
    """
    linter.register_checker(AugmentAssignments(linter))
    linter.register_checker(ImproveForLoop(linter))
    linter.register_checker(SimplifiableIf(linter))
