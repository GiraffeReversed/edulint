from astroid import nodes  # type: ignore
from typing import TYPE_CHECKING, Optional, List, Tuple, Union

from pylint.checkers import BaseChecker  # type: ignore

if TYPE_CHECKING:
    from pylint.lint import PyLinter  # type: ignore

from edulint.linting.checkers.utils import get_name, get_assigned_to, is_any_assign, is_builtin
from edulint.linting.checkers.modified_listener import ModifiedListener


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
            if self.was_reassigned(self.structure, allow_definition=False) \
                    or self.was_reassigned(self.index, allow_definition=False):
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
                    or self.was_reassigned(name, allow_definition=False):
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
        ),
        "R6206": (
            "Both branches should return a value explicitly (one returns implicit None)",
            "no-value-in-one-branch-return",
            "Emitted when one branch returns a value and the other just returns."
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
        return (node1 is None and node2 is None) \
             or (node1 is not None and node2 is not None and node1.as_string() == node2.as_string())

    def _mergeable(self, node1: nodes.NodeNG, node2: nodes.NodeNG) -> bool:
        if not isinstance(node1, type(node2)):
            return False

        if isinstance(node1, nodes.Return):
            return node1.value is not None and node2.value is not None

        if is_any_assign(node1) and not isinstance(node1, nodes.For):
            assigned_to1 = get_assigned_to(node1)
            assigned_to2 = get_assigned_to(node2)
            return len(assigned_to1) == 1 and len(assigned_to1) == len(assigned_to2) \
                and isinstance(assigned_to1[0], type(assigned_to2[0])) \
                and not isinstance(assigned_to1[0], nodes.Subscript) \
                and self._names_assigned_to(node1) == self._names_assigned_to(node2)

        return False

    def _merge_sequential(self, node: nodes.If) -> None:
        second_if = node.next_sibling()

        if isinstance(node.test, nodes.BoolOp) or isinstance(second_if.test, nodes.BoolOp) \
                or len(second_if.orelse) != 0 or len(node.body) != 1 or len(second_if.body) != 1:
            return

        body1 = node.body[0]
        body2 = second_if.body[0]
        if not isinstance(body1, type(body2)) \
                or not isinstance(body1, nodes.Return) \
                or not self._same_values(body1.value, body2.value):
            return

        parent_body = node.parent.body
        if all(isinstance(n, nodes.If) or isinstance(n, nodes.Return)
                or (is_any_assign(n) and not isinstance(n, nodes.For)) for n in parent_body) \
                and sum(1 if isinstance(n, nodes.If) else 0 for n in parent_body) > 2:
            return

        refactored = self._get_refactored(node.test, "or", second_if.test)
        self.add_message("simplifiable-if-merge", node=node, args=(refactored))

    def _is_just_returning_if(self, node: Optional[nodes.NodeNG]) -> bool:
        return node is not None and isinstance(node, nodes.If) and isinstance(node.body[-1], nodes.Return)

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

        if isinstance(then, nodes.Return) and isinstance(orelse, nodes.Return) \
                and (then.value is None) != (orelse.value is None):
            self.add_message("no-value-in-one-branch-return", node=node)
            return

        if not self._mergeable(then, orelse):
            return

        if len(node.orelse) == 0 and self._is_just_returning_if(node.previous_sibling()):
            return

        refactored = self._refactored_cond_from_then_orelse(node, then.value, orelse.value)

        if refactored is not None:
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


class NoGlobalVars(BaseChecker):
    name = "no-global-variables"
    msgs = {
        "R6401": (
            "Do not use global variables; you use %s, modifying it for example at line %i.",
            "no-global-vars",
            "Emitted when the code uses global variables."
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
                    nonglobal_modifiers = [n for n in listener.get_all_modifiers(node) if n.scope() != node.scope()]
                    if nonglobal_modifiers:
                        self.add_message("no-global-vars", node=node, args=(node.name, nonglobal_modifiers[0].lineno))


def register(linter: "PyLinter") -> None:
    """This required method auto registers the checker during initialization.
    :param linter: The linter to register the checker to.
    """
    linter.register_checker(ImproveForLoop(linter))
    linter.register_checker(SimplifiableIf(linter))
    linter.register_checker(NoGlobalVars(linter))
