from astroid import nodes  # type: ignore
from typing import TYPE_CHECKING, Optional, Tuple

from pylint.checkers import BaseChecker  # type: ignore
from pylint.checkers.utils import only_required_for_messages

if TYPE_CHECKING:
    from pylint.lint import PyLinter  # type: ignore

from edulint.linting.checkers.utils import get_name, get_assigned_to, is_any_assign


class SimplifiableIf(BaseChecker):  # type: ignore

    name = "simplifiable-if"
    msgs = {
        "R6201": (
            "The if statement can be replaced with 'return %s'",
            "simplifiable-if-return",
            "Emitted when returning a boolean value can be simplified.",
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
        ),
        "R6207": (
            "The if statement can be merged with the nested one to 'if %s:'",
            "simplifiable-if-nested",
            "Emitted when an if statement can be merged with its nested if."
        ),
        "R6208": (
            "The if statement can be merged with the following one to 'if %s:'",
            "simplifiable-if-seq",
            "Emitted when an if statement can be merged with the next using a logical operator"
        ),
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
        self.add_message("simplifiable-if-nested", node=node, args=refactored)

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
        self.add_message("simplifiable-if-seq", node=node, args=(refactored))

    def _is_just_returning_if(self, node: Optional[nodes.NodeNG]) -> bool:
        return node is not None and isinstance(node, nodes.If) and isinstance(node.body[-1], nodes.Return)

    @only_required_for_messages("simplifiable-if-return", "simplifiable-if-assignment",
                                "simplifiable-if-pass", "no-value-in-one-branch-return",
                                "simplifiable-if-nested", "simplifiable-if-seq")
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

    @only_required_for_messages("simplifiable-if-expr")
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
    linter.register_checker(SimplifiableIf(linter))
