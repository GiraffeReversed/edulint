from astroid import nodes  # type: ignore
from astroid.const import Context
from typing import TYPE_CHECKING, Optional, Tuple, Union, List, Any, Dict, Set
from enum import Enum

from pylint.checkers import BaseChecker  # type: ignore
from pylint.checkers.utils import only_required_for_messages

if TYPE_CHECKING:
    from pylint.lint import PyLinter  # type: ignore

from edulint.linting.checkers.utils import (
    get_name,
    get_assigned_to,
    is_any_assign,
    is_pure_builtin,
    get_const_value,
)

ExprRepresentation = str
Comparison = str
Value = Any
NodeCmpValue = Optional[Tuple[nodes.NodeNG, Comparison, Value]]
SameDirComparisons = Dict[
    ExprRepresentation, Dict[Comparison, Tuple[List[ExprRepresentation], List[bool]]]
]
# When you take a key (1), then one key (cmp) from the corresponding dictionary and an element from the
# first array from its corresponding value (2), you get a comparison ((1) (cmp) (2)). The List[bool]
# indicates, whether the comparison in the original source code is in the same direction as in the dictionary.


def is_modulo_residue(value: Any, modulo: int) -> bool:
    return isinstance(value, int) and 0 <= value < modulo


class Comparisons(Enum):
    EQUALITY = 0
    INEQUALITY = 1
    OTHER = 2


# I use this to represent all the pairs of type 'x % 2 == 0 and y % 2 != 1'
# expression_pair is the ('x', 'y'), modulo is 2, comparisons_for_equality is {},
# comparisons_for_inequality is [{0}, {}],
# comparisons_for_true is [{0}, {}] and
# comparisons_pairs is [('x % 2 == 0 and y % 2 != 1', Comparisons.OTHER)]
# Note that we have some redundancy here, but this makes the code easier later and
# this is not some code that would be run all the time, in fact it is quite rare.
class PairsOfModComparisonsWithNum:
    def __init__(
        self,
        expr1: ExprRepresentation,
        cmp1: Comparison,
        value1: Value,
        expr2: ExprRepresentation,
        cmp2: Comparison,
        value2: Value,
        modulo: int,
        comparison_pair_string: str,
    ) -> None:
        # the two expressions that have modulo applied to them
        self.expression_pair = (expr1, expr2)
        self.modulo = modulo

        # for expressions of type 'x % n == a and y % n == a' we add to this set the 'a'
        self.comparisons_for_equality: Set[int] = set()

        # stores expressions like 'expr1 % modulo == a and expr2 % modulo != b',
        # index represents the number that 'expr1 % modulo' is equal to and the set is
        # the set of all the values 'expr2 % modulo' could be equal to.
        self.comparisons_for_inequality: List[Set[int]] = [set() for _ in range(modulo)]
        self.comparisons_for_true: List[Set[int]] = [set() for _ in range(modulo)]

        # this is here so that we can easily get the original string
        self.comparisons_pairs: List[Tuple[str, Comparisons]] = []

        self.update(cmp1, value1, cmp2, value2, comparison_pair_string)

    def update_comparisons(
        self,
        comparisons: List[Set[int]],
        cmp1: Comparison,
        value1: Value,
        cmp2: Comparison,
        value2: Value,
    ) -> None:
        for v1 in self.get_possible_values_mod(cmp1, value1):
            comparisons[v1].update(self.get_possible_values_mod(cmp2, value2))

    def get_possible_values_mod(self, cmp1: Comparison, value1: Value) -> List[int]:
        # Note that here we use that for example 'x % 3 != 1' can be rewritten to 'x % 3 == 0 or x % 3 == 2'
        if cmp1 == "==":
            return [value1]

        return [i for i in range(self.modulo) if i != value1]

    def update(
        self,
        cmp1: Comparison,
        value1: Value,
        cmp2: Comparison,
        value2: Value,
        comparison_pair_string: str,
    ) -> None:
        if cmp1 == "==" and cmp2 == "==" and value1 == value2:
            self.comparisons_for_equality.add(value1)
            self.comparisons_pairs.append((comparison_pair_string, Comparisons.EQUALITY))
        elif (cmp1 == "==" and cmp2 == "==") or (
            (cmp1 != "!=" or cmp2 != "!=") and value1 == value2
        ):
            self.update_comparisons(self.comparisons_for_inequality, cmp1, value1, cmp2, value2)
            self.comparisons_pairs.append((comparison_pair_string, Comparisons.INEQUALITY))
        else:
            self.comparisons_pairs.append((comparison_pair_string, Comparisons.OTHER))

        self.update_comparisons(self.comparisons_for_true, cmp1, value1, cmp2, value2)

    def always_true(self) -> bool:
        for comparisons in self.comparisons_for_true:
            if len(comparisons) != self.modulo:
                return False

        return True

    def has_part_simplifiable_to_equality(self) -> bool:
        return len(self.comparisons_for_equality) == self.modulo

    def has_part_simplifiable_to_inequality(self) -> bool:
        for comparisons in self.comparisons_for_inequality:
            if len(comparisons) != self.modulo - 1:
                return False

        return True


class SimplifiableIf(BaseChecker):  # type: ignore
    name = "simplifiable-if"
    msgs = {
        "R6201": (
            "The if statement can be replaced with 'return %s'",
            "simplifiable-if-return",
            "Emitted when the condition of an if statement can be returned directly (possibly negated).",
        ),
        "R6202": (
            "The if statement can be replaced with 'return %s'",
            "simplifiable-if-return-conj",
            "Emitted when the condition of an if statement and the returned values "
            "can be combined using logical operators.",
        ),
        "R6203": (
            "The conditional assignment can be replaced with '%s = %s'",
            "simplifiable-if-assignment",
            "Emitted when the condition of an if statement can be assigned directly (possibly negated).",
        ),
        "R6210": (
            "The conditional assignment can be replaced with '%s = %s'",
            "simplifiable-if-assignment-conj",
            "Emitted when the condition of an if statement and the assigned values "
            "can be combined using logical operators.",
        ),
        "R6204": (
            "The if expression can be replaced with '%s'",
            "simplifiable-if-expr",
            "Emitted when the condition of an if expression can be returned directly (possibly negated).",
        ),
        "R6209": (
            "The if expression can be replaced with '%s'",
            "simplifiable-if-expr-conj",
            "Emitted when the condition of an if expression and the returned values "
            "can be combined using logical operators.",
        ),
        "R6205": (
            "Use 'if %s: <else body>' instead of 'pass'",
            "simplifiable-if-pass",
            "Emitted when there is an if condition with a pass in the positive branch.",
        ),
        "R6206": (
            "Both branches should return a value explicitly (one returns implicit None)",
            "no-value-in-one-branch-return",
            "Emitted when one branch returns a value and the other just returns.",
        ),
        "R6207": (
            "The if statement can be merged with the nested one to 'if %s:'",
            "simplifiable-if-nested",
            "Emitted when the condition of an if statement can be merged "
            "with its nested if's condition using logical operators.",
        ),
        "R6208": (
            "The if statement can be merged with the following one to 'if %s:'",
            "simplifiable-if-seq",
            "Emitted when the condition of an if statement can be merged "
            "with the next if's condition using logical operators.",
        ),
        "R6211": (
            "'%s' can be replaced with '%s'",
            "simplifiable-with-abs",
            "Emitted when there is a problem like x < 4 and x > -4 and suggests abs(x) < 4.",
        ),
        "R6212": (
            "'%s' can be simplified to '%s'. Simplify the condition if it is on purpose, or change it if it was not.",
            "redundant-compare-in-condition",
            "Emitted when there is a problem like x > 4 or x > 3 and suggests x > 3. (ie min{4, 3})",
        ),
        "R6213": (
            "'%s' can be replaced with '%s'",
            "redundant-compare-avoidable-with-max-min",
            "Emitted when there is a problem like 'x > a and x > b' and suggests x > max(a, b).",
        ),
        "R6214": (
            "'%s' can be replaced with '%s'",
            "using-compare-instead-of-equal",
            "Emitted when there is a problem like x >= 0 and x <= 0 and suggests x == 0.",
        ),
        "R6215": (
            "'%s' can be replaced with '%s'",
            "simplifiable-test-by-equals",
            "Emitted when there is a problem like 'x % 2 == 0 and y % 2 == 0 or x % 2 == 1 and y % 2 == 1' and suggests 'x % 2 == y % 2'.",
        ),
    }

    def _is_bool(self, node: nodes.NodeNG) -> bool:
        return isinstance(node, nodes.Const) and node.pytype() == "builtins.bool"

    def _simplifiable_if_message(
        self, node: nodes.If, then: nodes.NodeNG, new_cond: str, only_replaces: bool
    ) -> None:
        extra = "" if only_replaces else "-conj"
        if isinstance(node, nodes.IfExp):
            self.add_message("simplifiable-if-expr" + extra, node=node, args=(new_cond))
        elif isinstance(then, nodes.Return):
            self.add_message("simplifiable-if-return" + extra, node=node, args=(new_cond))
        else:
            self.add_message(
                "simplifiable-if-assignment" + extra,
                node=node,
                args=(get_name(get_assigned_to(then)[0]), new_cond),
            )

    def _get_refactored(self, *args: Union[str, nodes.NodeNG]) -> str:
        result = []
        i = 0
        while i < len(args):
            arg = args[i]
            if isinstance(arg, str) and arg == "not":
                v = args[i + 1]
                assert isinstance(v, nodes.NodeNG)
                refactored = v.as_string()
                if isinstance(v, nodes.BoolOp):
                    result.append(f"<negated ({refactored})>")
                else:
                    result.append(f"<negated {refactored}>")
                i += 2
            elif isinstance(arg, str) and arg in ("and", "or"):
                prev = args[i - 1]
                next_ = args[i + 1]
                if (
                    isinstance(prev, nodes.BoolOp)
                    and prev.op != arg
                    and (i - 2 < 0 or args[i - 2] != "not")
                ):
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

    def _names_assigned_to(self, node: nodes.NodeNG) -> List[str]:
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

    def _refactored_cond_from_then_orelse(
        self, node: nodes.If, then_value: nodes.NodeNG, orelse_value: nodes.NodeNG
    ) -> Optional[Tuple[str, bool]]:
        then_bool_value = then_value.value if self._is_bool(then_value) else None
        orelse_bool_value = orelse_value.value if self._is_bool(orelse_value) else None

        if then_bool_value is None and orelse_bool_value is None:
            return None

        if then_bool_value is not None and orelse_bool_value is not None:
            if then_bool_value and not orelse_bool_value:
                return self._get_refactored(node.test), True
            if not then_bool_value and orelse_bool_value:
                return self._get_refactored("not", node.test), True
            return None

        if then_bool_value is not None and then_bool_value:
            return self._get_refactored(node.test, "or", orelse_value), False

        if then_bool_value is not None and not then_bool_value:
            return self._get_refactored("not", node.test, "and", orelse_value), False

        if orelse_bool_value is not None and orelse_bool_value:
            return self._get_refactored("not", node.test, "or", then_value), False

        if orelse_bool_value is not None and not orelse_bool_value:
            return self._get_refactored(node.test, "and", then_value), False

        assert False, "unreachable"

    def _merge_nested(self, node: nodes.If) -> None:
        refactored = self._get_refactored(node.test, "and", node.body[0].test)
        self.add_message("simplifiable-if-nested", node=node, args=refactored)

    def _same_values(self, node1: nodes.NodeNG, node2: nodes.NodeNG) -> bool:
        return (node1 is None and node2 is None) or (
            node1 is not None and node2 is not None and node1.as_string() == node2.as_string()
        )

    def _mergeable(self, node1: nodes.NodeNG, node2: nodes.NodeNG) -> bool:
        if not isinstance(node1, type(node2)):
            return False

        if isinstance(node1, nodes.Return):
            return node1.value is not None and node2.value is not None

        if is_any_assign(node1) and not isinstance(node1, nodes.For):
            assigned_to1 = get_assigned_to(node1)
            assigned_to2 = get_assigned_to(node2)
            return (
                len(assigned_to1) == 1
                and len(assigned_to1) == len(assigned_to2)
                and isinstance(assigned_to1[0], type(assigned_to2[0]))
                and not isinstance(assigned_to1[0], nodes.Subscript)
                and self._names_assigned_to(node1) == self._names_assigned_to(node2)
            )

        return False

    def _merge_sequential(self, node: nodes.If) -> None:
        second_if = node.next_sibling()

        if (
            isinstance(node.test, nodes.BoolOp)
            or isinstance(second_if.test, nodes.BoolOp)
            or len(second_if.orelse) != 0
            or len(node.body) != 1
            or len(second_if.body) != 1
        ):
            return

        body1 = node.body[0]
        body2 = second_if.body[0]
        if (
            not isinstance(body1, type(body2))
            or not isinstance(body1, nodes.Return)
            or not self._same_values(body1.value, body2.value)
        ):
            return

        parent_body = node.parent.body
        if (
            all(
                isinstance(n, nodes.If)
                or isinstance(n, nodes.Return)
                or (is_any_assign(n) and not isinstance(n, nodes.For))
                for n in parent_body
            )
            and sum(1 if isinstance(n, nodes.If) else 0 for n in parent_body) > 2
        ):
            return

        refactored = self._get_refactored(node.test, "or", second_if.test)
        self.add_message("simplifiable-if-seq", node=node, args=(refactored))

    def _is_just_returning_if(self, node: Optional[nodes.NodeNG]) -> bool:
        return (
            node is not None
            and isinstance(node, nodes.If)
            and isinstance(node.body[-1], nodes.Return)
        )

    @only_required_for_messages(
        "simplifiable-if-return",
        "simplifiable-if-return-conj",
        "simplifiable-if-assignment",
        "simplifiable-if-assignment-conj",
        "simplifiable-if-pass",
        "no-value-in-one-branch-return",
        "simplifiable-if-nested",
        "simplifiable-if-seq",
    )
    def visit_if(self, node: nodes.If) -> None:
        if len(node.orelse) == 0:
            if (
                len(node.body) == 1
                and isinstance(node.body[0], nodes.If)
                and len(node.body[0].orelse) == 0
            ):
                self._merge_nested(node)
                return

            if node.next_sibling() is not None and isinstance(node.next_sibling(), nodes.If):
                self._merge_sequential(node)
                return

        if len(node.body) == 1 and isinstance(node.body[0], nodes.Pass) and len(node.orelse) > 0:
            self.add_message(
                "simplifiable-if-pass", node=node, args=(self._get_refactored("not", node.test))
            )
            return

        then_orelse = self._get_then_orelse(node)

        if not then_orelse:
            return

        then, orelse = then_orelse

        if (
            isinstance(then, nodes.Return)
            and isinstance(orelse, nodes.Return)
            and (then.value is None) != (orelse.value is None)
        ):
            self.add_message("no-value-in-one-branch-return", node=node)
            return

        if not self._mergeable(then, orelse):
            return

        if len(node.orelse) == 0 and self._is_just_returning_if(node.previous_sibling()):
            return

        refactored = self._refactored_cond_from_then_orelse(node, then.value, orelse.value)

        if refactored is not None:
            new_cond, only_replaces = refactored
            self._simplifiable_if_message(node, then, new_cond, only_replaces)

    @only_required_for_messages("simplifiable-if-expr", "simplifiable-if-expr-conj")
    def visit_ifexp(self, node: nodes.IfExp) -> None:
        then, orelse = node.body, node.orelse
        assert then is not None and orelse is not None

        if (not isinstance(then, nodes.Const) and not isinstance(then, nodes.Name)) or (
            not isinstance(orelse, nodes.Const) and not isinstance(orelse, nodes.Name)
        ):
            return

        refactored = self._refactored_cond_from_then_orelse(node, then, orelse)
        if refactored is not None:
            new_cond, only_replaces = refactored
            self._simplifiable_if_message(node, then, new_cond, only_replaces)

    SWITCHED_COMPARATOR = {
        ">=": "<=",
        ">": "<",
        "<=": ">=",
        "<": ">",
    }

    EQ_NEQ = {"==", "!="}

    def _get_values_and_comparator(
        self, node: nodes.Compare
    ) -> Tuple[nodes.NodeNG, str, nodes.NodeNG]:
        """
        This method assumes node is a comparison between just two values.
        """
        left, (comp, right) = node.left, node.ops[0]
        return left, comp, right

    def _is_number(self, node: nodes.NodeNG) -> bool:
        const_val = get_const_value(node)
        return isinstance(const_val, (int, float)) and not isinstance(const_val, bool)

    def _get_node_comparator_const_value(self, node: nodes.NodeNG) -> NodeCmpValue:
        """
        Assumes that node is a child of Bool Op.
        If the extraction was not successful returns None.
        It is succesful if and only if it is an inequality between
        a constant and a non-constant.

        When this does not return None, the constant is last.
        """
        if not isinstance(node, nodes.Compare) or len(node.ops) >= 2:
            return None

        left, comp, right = self._get_values_and_comparator(node)

        left_is_number = self._is_number(left)
        right_is_number = self._is_number(right)

        if (
            (left_is_number and right_is_number)
            or (not left_is_number and not right_is_number)
            or comp not in self.SWITCHED_COMPARATOR
        ):
            return None

        if left_is_number:
            left, comp, right = right, self.SWITCHED_COMPARATOR[comp], left

        return left, comp, get_const_value(right)

    def _get_comparator_by_restriction(self, cmp1: str, cmp2: str, more_restrictive: bool) -> str:
        if len(cmp1) > len(cmp2):
            cmp1, cmp2 = cmp2, cmp1

        return cmp1 if more_restrictive else cmp2

    def _remove_redundant_compare(
        self, cmp1: str, const1: Any, cmp2: str, const2: Any, is_and: bool
    ) -> Tuple[str, int]:
        """
        Supposes that cmp1 and cmp2 are comparisons in the same direction (i.e. > and >=, ...)
        and that const1 and const2 are both numric values.

        <is_and> is True when there is <and> operation between the two comparisons and
        is False when there is <or> between them.
        """
        if const1 == const2:
            return [self._get_comparator_by_restriction(cmp1, cmp2, is_and), const1]

        # make the const1 smaller than const2
        if const1 > const2:
            cmp1, const1, cmp2, const2 = cmp2, const2, cmp1, const1

        if cmp1 == ">" or cmp1 == ">=":
            if is_and:
                return [cmp2, const2]
            return [cmp1, const1]

        if is_and:
            return [cmp1, const1]

        return [cmp2, const2]

    def _add_abs_if_necessary(self, expr_string: str) -> str:
        if expr_string.startswith("abs("):
            return expr_string + " "

        return "abs(" + expr_string + ") "

    def _check_for_simplification_of_single_or(
        self, const1: Any, cmp1: str, const2: Any, cmp2: str, expr_string: str
    ) -> str:
        """
        Supposes that <expr_string> is a variable name or is of type f(x), where
        f is pure builtin function.

        And checks if an expression <<expr_string> <cmp1> <const1> or
        <expr_string> <cmp2> <const2>> can be simplified.

        Checks for problems like 'f(x) >= 4 or f(x) <= -4' and suggests to
        replace them with 'abs(f(x)) >= 4'.

        Returns the suggestion as a string.
        """
        new_expr = "True"

        if cmp1 in {">=", ">"}:
            if const1 > 0:
                new_expr = self._add_abs_if_necessary(expr_string) + cmp1 + " " + str(const1)
        else:
            if const1 < 0:
                new_expr = self._add_abs_if_necessary(expr_string) + cmp2 + " " + str(const2)

        return new_expr

    def _check_for_simplification_of_single_and(
        self, const1: Any, cmp1: str, const2: Any, cmp2: str, expr_string: str
    ) -> str:
        """
        Supposes that <expr_string> is a variable name or is of type f(x), where
        f is pure builtin function. And also supposes that cmp1 and cmp2 are in
        opposite directions.

        And checks if an expression <<expr_string> <cmp1> <const1> and
        <expr_string> <cmp2> <const2>> can be simplified.

        Checks for problems like 'f(x) < 4 and f(x) > -4' and suggests to
        replace them with 'abs(f(x)) < 4'.

        Returns the suggestion as a string.
        """
        new_expr = "False"

        if cmp1 in {">=", ">"}:
            if const1 < 0:
                new_expr = self._add_abs_if_necessary(expr_string) + cmp2 + " " + str(const2)
        else:
            if const1 > 0:
                new_expr = self._add_abs_if_necessary(expr_string) + cmp1 + " " + str(const1)

        return new_expr

    def _check_if_always_true_or_false(
        self, const1: Any, cmp1: str, const2: Any, cmp2: str, expr_string: str, op: str
    ) -> str:
        if const1 == const2:
            if len(cmp1) == 1 and len(cmp2) == 1 and op == "or":
                return expr_string + " != " + str(const1)

            if len(cmp1) == 2 and len(cmp2) == 2 and op == "and":
                return expr_string + " == " + str(const1)

            if op == "or":
                return "True"

            return "False"

        if op == "and" and (
            (const1 < const2 and cmp1[0] == "<") or (const1 > const2 and cmp2[0] == "<")
        ):
            return "False"

        if op == "or" and (
            (const1 < const2 and cmp1[0] == ">") or (const1 > const2 and cmp2[0] == ">")
        ):
            return "True"

        return ""

    def _get_group_as_string(
        self, expr_string: str, group: List[Tuple[Comparison, Value]], op: str
    ) -> str:
        result = []

        for i in range(len(group)):
            cmp, val = group[i]
            result.extend([expr_string, cmp, str(val)])
            if i < len(group) - 1:
                result.append(op)

        return " ".join(result)

    def _suggestion_for_group_of_boolops(
        self, expr_string: str, group: List[Tuple[Comparison, Value]], node: nodes.BoolOp
    ) -> None:
        # We'll use commutativity of boolean operations and group the comparisons in same direction
        # (< with <= and > with >=) and simplify the grouped parts and then we can simplify the rest.
        cmp_less, val1 = None, None
        cmp_greater, val2 = None, None
        changed = False

        for cmp, val in group:
            if cmp[0] == "<":
                if cmp_less is None:
                    cmp_less, val1 = cmp, val
                    continue
                changed = True
                cmp_less, val1 = self._remove_redundant_compare(
                    cmp_less, val1, cmp, val, node.op == "and"
                )
            else:
                if cmp_greater is None:
                    cmp_greater, val2 = cmp, val
                    continue
                changed = True
                cmp_greater, val2 = self._remove_redundant_compare(
                    cmp_greater, val2, cmp, val, node.op == "and"
                )

        group_string = self._get_group_as_string(expr_string, group, node.op)

        if cmp_less is None:
            self.add_message(
                "redundant-compare-in-condition",
                node=node,
                args=(group_string, " ".join([expr_string, cmp_greater, str(val2)])),
            )
            return

        if cmp_greater is None:
            self.add_message(
                "redundant-compare-in-condition",
                node=node,
                args=(group_string, " ".join([expr_string, cmp_less, str(val1)])),
            )
            return

        new_expr = self._check_if_always_true_or_false(
            val1, cmp_less, val2, cmp_greater, expr_string, node.op
        )

        if len(new_expr) != 0:
            self.add_message(
                (
                    "redundant-compare-in-condition"
                    if new_expr == "True" or new_expr == "False"
                    else "using-compare-instead-of-equal"
                ),
                node=node,
                args=(group_string, new_expr),
            )
            return

        if val1 != -val2 or cmp_less != self.SWITCHED_COMPARATOR[cmp_greater]:
            if changed:
                self.add_message(
                    "redundant-compare-in-condition",
                    node=node,
                    args=(
                        group_string,
                        " ".join(
                            [
                                expr_string,
                                cmp_less,
                                str(val1),
                                node.op,
                                expr_string,
                                cmp_greater,
                                str(val2),
                            ]
                        ),
                    ),
                )
            return

        if node.op == "and":
            new_expr = self._check_for_simplification_of_single_and(
                val1, cmp_less, val2, cmp_greater, expr_string
            )
        else:
            new_expr = self._check_for_simplification_of_single_or(
                val1, cmp_less, val2, cmp_greater, expr_string
            )

        self.add_message(
            "simplifiable-with-abs",
            node=node,
            args=(group_string, new_expr),
        )

    def _is_pure_node(self, node: nodes.NodeNG):
        """
        Note: This method does not check children of the node, just the node itself.
        """
        return (
            isinstance(node, nodes.Name)
            or isinstance(node, nodes.Const)
            or isinstance(node, nodes.BinOp)
            or isinstance(node, nodes.BoolOp)
            or isinstance(node, nodes.UnaryOp)
            or isinstance(node, nodes.Compare)
            or (isinstance(node, nodes.Subscript) and node.ctx == Context.Load)
            or isinstance(node, nodes.Attribute)
            or (
                isinstance(node, nodes.Call)
                and len(node.keywords) == 0
                and len(node.kwargs) == 0
                and len(node.starargs) == 0
                and is_pure_builtin(node.func)
            )
        )

    def _is_pure_expression(self, node: nodes.NodeNG) -> bool:
        if not self._is_pure_node(node):
            return False

        children = node.get_children()
        if isinstance(node, nodes.Call):
            # the first child of Call is always the function itself and we know it is pure by now.
            next(children)

        for child in children:
            if not self._is_pure_expression(child):
                return False

        return True

    def _group_and_check_by_representation(
        self, comparison_operands: List[NodeCmpValue], node: nodes.BoolOp
    ) -> None:
        already_checked: Set[int] = set()
        current_group: List[Tuple[Comparison, Value]] = []

        for i in range(len(comparison_operands)):
            if i in already_checked:
                continue

            expr1, cmp1, const1 = comparison_operands[i]
            current_group = [(cmp1, const1)]
            for j in range(i + 1, len(comparison_operands)):
                if j in already_checked:
                    continue

                expr2, cmp2, const2 = comparison_operands[j]
                # I could have done something more, but thanks to how as_string returns same string
                # even if there are some additional parentheses or spaces this seems good enough.
                # Could be improved with checking the actual structure and types of expr1 and expr2,
                # but with the knowledge that all the operands are pure and are from the same bool
                # expression we can safely just check using as_string().
                if expr1.as_string() == expr2.as_string():
                    current_group.append((cmp2, const2))
                    already_checked.add(j)

            if len(current_group) < 2:
                continue

            self._suggestion_for_group_of_boolops(expr1.as_string(), current_group, node)

    def _update_comparisons(
        self,
        comparisons: SameDirComparisons,
        expr1: str,
        comparator: str,
        expr2: str,
        comparison_switched: bool,
    ):
        if expr1 in comparisons:
            if comparator in comparisons[expr1]:
                comparisons[expr1][comparator][0].append(expr2)
                comparisons[expr1][comparator][1].append(comparison_switched)
            else:
                comparisons[expr1][comparator] = ([expr2], [comparison_switched])
        else:
            comparisons[expr1] = {comparator: ([expr2], [comparison_switched])}

    def _switch_if_necessary(
        self, expr1: str, cmp: str, expr2: str, was_switched: bool
    ) -> List[str]:
        if was_switched:
            return [expr2, self.SWITCHED_COMPARATOR[cmp], expr1]

        return [expr1, cmp, expr2]

    def _get_original_group_as_string(
        self,
        expr_string: str,
        cmp: str,
        group: List[ExprRepresentation],
        was_switched: List[bool],
        compared_with_num: Optional[Tuple[str, bool]],
        op: str,
    ) -> str:
        result = []

        for i in range(len(group)):
            result.extend(self._switch_if_necessary(expr_string, cmp, group[i], was_switched[i]))

            if i < len(group) - 1:
                result.append(op)

        if compared_with_num is not None:
            result.append(op)
            result.extend(
                self._switch_if_necessary(
                    expr_string,
                    cmp,
                    compared_with_num[0],
                    compared_with_num[1],
                )
            )

        return " ".join(result)

    def _put_into_max_or_min(
        self,
        function: str,
        expression: str,
        comparison: str,
        expressions: List[str],
        compared_with_num: Optional[Tuple[str, bool]],
        was_switched: List[bool],
    ) -> str:
        """
        the <function> should contain either "max(" or "min("
        """
        result: List[str] = [function]
        all_switched_or_all_not_switched = True

        for i in range(len(expressions)):
            if expressions[i].startswith(function):
                result.append(expressions[i][4:-1])
            else:
                result.append(expressions[i])

            all_switched_or_all_not_switched &= was_switched[i] == was_switched[0]

            if i < len(expressions) - 1:
                result.append(", ")

        if compared_with_num is not None:
            all_switched_or_all_not_switched &= compared_with_num[1] == was_switched[0]

            result.append(", ")
            result.append(compared_with_num[0])

        result.append(")")

        if (all_switched_or_all_not_switched and was_switched[0]) or (
            not all_switched_or_all_not_switched and comparison[0] == ">"
        ):
            return "".join(result) + f" {self.SWITCHED_COMPARATOR[comparison]} {expression}"

        return f"{expression} {comparison} " + "".join(result)

    def _make_suggestion_for_using_max_min_if_possible(
        self,
        comparisons_with_numbers: SameDirComparisons,
        comparisons: SameDirComparisons,
        node: nodes.BoolOp,
    ) -> None:
        """
        Makes suggestion only for the comparisons that will maximize the number of
        comparisons put together with max (ie. in here: "x > a and b < x and b < 1
        and a > b" would suggest "x > a and b < min(x, 1, a)" instead of
        "x > max(a, b) and b < 1 and b < a"). And makes only one suggestion (after
        finding the suggestion as described earlier the method just returns).
        """
        expression: Optional[str] = None
        comparison: Optional[str] = None
        expressions: Optional[List[str]] = None
        was_switched: Optional[List[bool]] = None
        compared_with_num: Optional[Tuple[str, bool]] = None

        for expr, compared_with in comparisons.items():
            for cmp, exprs in compared_with.items():
                if len(exprs[0]) < 2:
                    continue

                comparison_count = len(exprs[0])
                compared_with_1_number = False
                # note: when it's compared with multiple numbers the redundant compare in condition
                # or simplifiable-with-abs could make a suggestion and I don't want to make
                # conflicting suggestions.

                if (
                    expr in comparisons_with_numbers
                    and len(comparisons_with_numbers[expr]) == 1
                    and cmp in comparisons_with_numbers[expr]
                    and len(comparisons_with_numbers[expr][cmp][0]) == 1
                ):
                    comparison_count += 1
                    compared_with_1_number = True

                if expression is None or len(expressions) < comparison_count:
                    expression = expr
                    comparison = cmp
                    expressions, was_switched = exprs

                    if compared_with_1_number:
                        compared_with_num = (
                            comparisons_with_numbers[expr][cmp][0][0],
                            comparisons_with_numbers[expr][cmp][1][0],
                        )
                    else:
                        compared_with_num = None

        if expression is None:
            return

        group_string = self._get_original_group_as_string(
            expression, comparison, expressions, was_switched, compared_with_num, node.op
        )

        func = (
            "max("
            if (
                (node.op == "and" and comparison[0] == ">")
                or (node.op == "or" and comparison[0] == "<")
            )
            else "min("
        )

        self.add_message(
            "redundant-compare-avoidable-with-max-min",
            node=node,
            args=(
                group_string,
                self._put_into_max_or_min(
                    func, expression, comparison, expressions, compared_with_num, was_switched
                ),
            ),
        )

    def _is_equality_or_inequality(self, node: nodes.NodeNG) -> bool:
        return (
            isinstance(node, (nodes.Compare))
            and len(node.ops) == 1
            and node.ops[0][0] in self.EQ_NEQ
        )

    def _is_conjunction_of_two_equalities(self, node: nodes.NodeNG) -> bool:
        return (
            isinstance(node, nodes.BoolOp)
            and node.op == "and"
            and len(node.values) == 2
            and self._is_equality_or_inequality(node.values[0])
            and self._is_equality_or_inequality(node.values[1])
        )

    def _add_parentheses_to_operations(self, node: nodes.NodeNG) -> str:
        if isinstance(node, (nodes.BinOp, nodes.BoolOp, nodes.UnaryOp, nodes.Compare)):
            return f"({node.as_string()})"

        return node.as_string()

    def _destructure_mod_and_number_comparison(
        self, node: nodes.Compare
    ) -> Optional[Tuple[ExprRepresentation, int, Comparison, Value]]:
        left, cmp, right = self._get_values_and_comparator(node)

        left_is_number = self._is_number(left)
        right_is_number = self._is_number(right)

        if (left_is_number and right_is_number) or (not left_is_number and not right_is_number):
            return None

        if left_is_number:
            left, cmp, right = right, cmp, left

        if not isinstance(left, nodes.BinOp) or left.op != "%" or not self._is_number(left.right):
            return None

        mod = get_const_value(left.right)
        val = get_const_value(right)

        if not isinstance(mod, int) or not is_modulo_residue(val, mod):
            return None

        if mod == 2 and cmp == "!=":
            cmp = "=="
            val = 1 - val

        return self._add_parentheses_to_operations(left.left), mod, cmp, val

    def _destructure_mod_and_number_comps(
        self, left: nodes.Compare, right: nodes.Compare
    ) -> Optional[
        Tuple[ExprRepresentation, Comparison, Value, ExprRepresentation, Comparison, Value, int]
    ]:
        left_comparison = self._destructure_mod_and_number_comparison(left)
        right_comparison = self._destructure_mod_and_number_comparison(right)

        if (
            left_comparison is None
            or right_comparison is None
            or left_comparison[1] != right_comparison[1]
        ):
            return None

        return (
            left_comparison[0],
            left_comparison[2],
            left_comparison[3],
            right_comparison[0],
            right_comparison[2],
            right_comparison[3],
            left_comparison[1],
        )

    def _insert_conjuncted_mod_comparison(
        self,
        modulo_connected_with_and: List[PairsOfModComparisonsWithNum],
        expr1: ExprRepresentation,
        cmp1: Comparison,
        val1: Value,
        expr2: ExprRepresentation,
        cmp2: Comparison,
        val2: Value,
        mod: int,
        comparison_pair_string: str,
    ) -> None:
        for pair in modulo_connected_with_and:
            if pair.modulo != mod:
                continue

            if pair.expression_pair == (expr1, expr2):
                pair.update(cmp1, val1, cmp2, val2, comparison_pair_string)
                return

            if pair.expression_pair == (expr2, expr1):
                pair.update(cmp2, val2, cmp1, val1, comparison_pair_string)
                return

        modulo_connected_with_and.append(
            PairsOfModComparisonsWithNum(
                expr1, cmp1, val1, expr2, cmp2, val2, mod, comparison_pair_string
            )
        )

    def _make_suggestion_for_simplifiable_test_by_equals(
        self, modulo_connected_with_and: List[PairsOfModComparisonsWithNum], node: nodes.BoolOp
    ) -> None:
        for pair in modulo_connected_with_and:
            original: Optional[str] = None
            suggestion: Optional[str] = None

            if pair.always_true():
                original = " or ".join([expr for (expr, _) in pair.comparisons_pairs])
                suggestion = "True"
            elif pair.has_part_simplifiable_to_equality():
                original = " or ".join(
                    [
                        expr
                        for (expr, for_comparison) in pair.comparisons_pairs
                        if for_comparison == Comparisons.EQUALITY
                    ]
                )
                suggestion = f"{pair.expression_pair[0]} % {pair.modulo} == {pair.expression_pair[1]} % {pair.modulo}"
            elif pair.has_part_simplifiable_to_inequality():
                original = " or ".join(
                    [
                        expr
                        for (expr, for_comparison) in pair.comparisons_pairs
                        if for_comparison == Comparisons.INEQUALITY
                    ]
                )
                suggestion = f"{pair.expression_pair[0]} % {pair.modulo} != {pair.expression_pair[1]} % {pair.modulo}"

            if original is not None:
                self.add_message(
                    "simplifiable-test-by-equals",
                    node=node,
                    args=(original, suggestion),
                )

    def _is_comparison_not_between_numbers(self, node: nodes.NodeNG) -> bool:
        return (
            isinstance(node, nodes.Compare)
            and len(node.ops) == 1
            and node.ops[0][0] in self.SWITCHED_COMPARATOR
            and not self._is_number(node.left)
            and not self._is_number(node.ops[0][1])
        )

    def _check_for_simplification_of_boolop(self, node: nodes.BoolOp) -> None:
        if node.op is None:
            return

        comparison_operands: List[NodeCmpValue] = []
        comparisons_with_numbers: SameDirComparisons = {}
        comparisons: SameDirComparisons = {}

        node_is_or = node.op == "or"
        modulo_connected_with_and: List[PairsOfModComparisonsWithNum] = []

        for value in node.values:
            if not self._is_pure_expression(value):
                return

            operand = self._get_node_comparator_const_value(value)

            if operand is not None:
                comparison_operands.append(operand)
                self._update_comparisons(
                    comparisons_with_numbers,
                    operand[0].as_string(),
                    operand[1],
                    str(operand[2]),
                    value.ops[0][0] != operand[1],
                )
            elif self._is_comparison_not_between_numbers(value):
                self._update_comparisons(
                    comparisons,
                    value.left.as_string(),
                    value.ops[0][0],
                    value.ops[0][1].as_string(),
                    False,
                )
                self._update_comparisons(
                    comparisons,
                    value.ops[0][1].as_string(),
                    self.SWITCHED_COMPARATOR[value.ops[0][0]],
                    value.left.as_string(),
                    True,
                )
            elif node_is_or and self._is_conjunction_of_two_equalities(value):
                tmp = self._destructure_mod_and_number_comps(value.values[0], value.values[1])
                if tmp is not None:
                    self._insert_conjuncted_mod_comparison(
                        modulo_connected_with_and, *tmp, value.as_string()
                    )

        self._group_and_check_by_representation(comparison_operands, node)
        self._make_suggestion_for_using_max_min_if_possible(
            comparisons_with_numbers, comparisons, node
        )
        self._make_suggestion_for_simplifiable_test_by_equals(modulo_connected_with_and, node)

    @only_required_for_messages(
        "simplifiable-with-abs",
        "redundant-compare-in-condition",
        "redundant-compare-avoidable-with-max-min",
        "using-compare-instead-of-equal",
        "simplifiable-test-by-equals",
    )
    def visit_boolop(self, node: nodes.BoolOp) -> None:
        self._check_for_simplification_of_boolop(node)


def register(linter: "PyLinter") -> None:
    """This required method auto registers the checker during initialization.
    :param linter: The linter to register the checker to.
    """
    linter.register_checker(SimplifiableIf(linter))
