import sys

from astroid import nodes  # type: ignore
from typing import TYPE_CHECKING, Optional, List, Tuple, Union, Any

from pylint.checkers import BaseChecker
from pylint.checkers.utils import only_required_for_messages

if TYPE_CHECKING:
    from pylint.lint import PyLinter

from edulint.linting.checkers.utils import (
    get_range_params,
    get_const_value,
    infer_to_value,
    is_parents_elif,
    get_statements_count,
    is_pure_builtin,
    is_negation,
    get_name,
)


class Short(BaseChecker):
    name = "short-problems"
    msgs = {
        "R6601": (
            "Use %s.append(%s) instead of %s.",
            "use-append",
            "Emitted when code extends list by a single argument instead of appending it.",
        ),
        "R6602": (
            "Use integral division //.",
            "use-integral-division",
            "Emitted when the code uses float division and converts the result to int.",
        ),
        "R6603": (
            "Use isdecimal to test if string contains a number.",
            "use-isdecimal",
            "Emitted when the code uses isdigit or isnumeric.",
        ),
        "R6604": (
            "Do not use %s loop with else.",
            "no-loop-else",
            "Emitted when the code contains loop with else block.",
        ),
        "R6605": (
            "Use elif.",
            "use-elif",
            "Emitted when the code contains else: if construction instead of elif. Might return a false positive if "
            "the code mixes tabs and spaces.",
        ),
        "R6606": (
            "The for loop makes %s.",
            "at-most-one-iteration-for-loop",
            "Emitted when a for loop would always perform at most one iteration.",
        ),
        "R6607": (
            "Use %s instead of repeated %s in %s.",
            "no-repeated-op",
            "Emitted when the code contains repeated adition/multiplication instead of multiplication/exponentiation.",
        ),
        "R6608": (
            "Redundant arithmetic: %s",
            "redundant-arithmetic",
            "Emitted when there is redundant arithmetic (e.g. +0, *1) in an expression.",
        ),
        "R6609": (
            "Use augmented assignment: '%s %s= %s'",
            "use-augmented-assign",
            "Emitted when an assignment can be simplified by using its augmented version.",
        ),
        "R6610": (
            "Do not multiply list with mutable content.",
            "do-not-multiply-mutable",
            "Emitted when a list with mutable contents is being multiplied.",
        ),
        "R6611": (
            "Use else instead of elif.",
            "redundant-elif",
            "Emitted when the condition in elif is negation of the condition in the if.",
        ),
        "R6612": (
            "Unreachable else.",
            "unreachable-else",
            "Emitted when the else branch is unreachable due to totally exhaustive conditions before.",
        ),
        "R6613": (
            "Use '%s' directly rather than as '%s'.",
            "no-is-bool",
            "Emitted when the is operator is used with a bool value.",
        ),
        "R6614": (
            'Use "%s" instead of using the magical constant %i.',
            "use-ord-letter",
            "Emitted when the code uses a magical constant instead of a string literal.",
        ),
        "R6615": (
            "Remove the call to 'ord' and compare to the string directly \"%s\" instead of using "
            "the magical constant %i. Careful, this may require changing the comparison operator.",
            "use-literal-letter",
            "Emitted when the code uses a magical constant instead of a string literal in a comparison.",
        ),
        "R6616": (
            "Use early return.",
            "use-early-return",
            "Emitted when a long block of code is followed by an else that just returns, breaks or continues.",
        ),
        "R6617": (
            "The and operation can be replaced with '%s'",
            "simplifiable-single-and-with-abs",
            "Emitted when there is a problem like x < 4 and x > -4 and suggests abs(x) < 4.",
        ),
        "R6618": (
            "'%s' can be replaced with '%s'",
            "simplifiable-single-or-with-abs",
            "Emitted when there is a problem like x > 4 or x < -4 and suggests abs(x) > 4.",
        ),
        "R6619": (
            "'%s' can be replaced with '%s'",
            "simplifiable-and-with-abs",
            "Emitted when there is a problem like x < 4 and x > -4 and suggests abs(x) < 4."
            "But works with multiple and-s. (but is possibly slower than simplifiable-single-and-with-abs).",
        ),
        "R6620": (
            "'%s' can be replaced with '%s'",
            "simplifiable-or-with-abs",
            "Emitted when there is a problem like x > 4 or x < -4 and suggests abs(x) > 4."
            "But works with multiple and-s. (but is possibly slower than simplifiable-single-and-with-abs).",
        ),
        "R6621": (
            "'%s' can be replaced with '%s'",
            "redundant-compare-in-condition",
            "Emitted when there is a problem like x > 4 or x > 3 and suggests x > 3. (ie min{4, 3})",
        ),
    }

    def _check_extend(self, node: nodes.Call) -> None:
        if (
            isinstance(node.func, nodes.Attribute)
            and node.func.attrname == "extend"
            and len(node.args) == 1
            and isinstance(node.args[0], nodes.List)
            and len(node.args[0].elts) == 1
        ):
            self.add_message(
                "use-append",
                node=node,
                args=(
                    node.func.expr.as_string(),
                    node.args[0].elts[0].as_string(),
                    node.as_string(),
                ),
            )

    def _check_augassign_extend(self, node: nodes.AugAssign) -> None:
        if node.op == "+=" and isinstance(node.value, nodes.List) and len(node.value.elts) == 1:
            self.add_message(
                "use-append",
                node=node,
                args=(node.target.as_string(), node.value.elts[0].as_string(), node.as_string()),
            )

    def _check_isdecimal(self, node: nodes.Call) -> None:
        if isinstance(node.func, nodes.Attribute) and node.func.attrname in (
            "isdigit",
            "isnumeric",
        ):
            self.add_message("use-isdecimal", node=node)

    def _check_div(self, node: nodes.Call) -> None:
        if (
            isinstance(node.func, nodes.Name)
            and node.func.name == "int"
            and len(node.args) == 1
            and isinstance(node.args[0], nodes.BinOp)
            and node.args[0].op == "/"
        ):
            self.add_message("use-integral-division", node=node)

    def _check_loop_else(self, nodes: List[nodes.NodeNG], parent_name: str) -> None:
        if nodes:
            self.add_message("no-loop-else", node=nodes[0].parent, args=(parent_name))

    def _check_else_if(self, node: nodes.If) -> None:
        if node.has_elif_block():
            first_body = node.body[0]
            first_orelse = node.orelse[0]
            if first_body.col_offset == first_orelse.col_offset:
                self.add_message("use-elif", node=node.orelse[0])

    def _check_iteration_count(self, node: nodes.For) -> None:
        def get_const(node: nodes.NodeNG) -> Any:
            return node.value if isinstance(node, nodes.Const) else None

        range_params = get_range_params(node.iter)
        if range_params is None:
            return

        start, stop, step = range_params
        start, stop, step = get_const(start), get_const(stop), get_const(step)

        if start is not None and stop is not None and step is not None:
            if start >= stop:
                self.add_message(
                    "at-most-one-iteration-for-loop", node=node, args=("no iterations",)
                )
            elif start + step >= stop:
                self.add_message(
                    "at-most-one-iteration-for-loop", node=node, args=("only one iteration",)
                )

    def _check_repeated_operation_rec(
        self, node: nodes.NodeNG, op: str, name: Optional[str] = None
    ) -> Optional[Tuple[int, str]]:
        if isinstance(node, nodes.BinOp):
            if node.op != op:
                return None

            lt = self._check_repeated_operation_rec(node.left, op, name)
            if lt is None:
                return None

            count_lt, name_lt = lt
            assert name is None or name == name_lt
            rt = self._check_repeated_operation_rec(node.right, op, name_lt)
            if rt is None:
                return None

            count_rt, _ = rt
            return count_lt + count_rt, name

        if (
            name is None and type(node) in (nodes.Name, nodes.Attribute, nodes.Subscript)
        ) or name == node.as_string():
            return 1, node.as_string()
        return None

    def _check_repeated_operation(self, node: nodes.BinOp) -> None:
        if node.op in ("+", "*"):
            result = self._check_repeated_operation_rec(node, node.op)
            if result is None:
                return

            # DANGER: on some structures, + may be available but not *
            self.add_message(
                "no-repeated-op",
                node=node,
                args=(
                    "multiplication" if node.op == "+" else "exponentiation",
                    "addition" if node.op == "+" else "muliplication",
                    node.as_string(),
                ),
            )

    def _check_redundant_arithmetic(self, node: Union[nodes.BinOp, nodes.AugAssign]) -> None:
        if isinstance(node, nodes.BinOp):
            op = node.op
            left = get_const_value(node.left)
            right = get_const_value(node.right)
        elif isinstance(node, nodes.AugAssign):
            op = node.op[:-1]
            left = None
            right = get_const_value(node.value)
        else:
            assert False, "unreachable"

        if (
            (op == "+" and (left in (0, "") or right in (0, "")))
            or (op == "-" and (left == 0 or right == 0))
            or (op == "*" and (left in (0, 1) or right in (0, 1)))
            or (op == "/" and right == 1)
            or (
                op in ("/", "//", "%")
                and (
                    isinstance(node, nodes.BinOp)
                    and node.left.as_string() == node.right.as_string()
                    or isinstance(node, nodes.AugAssign)
                    and node.target.as_string() == node.value.as_string()
                )
            )
            or (op == "**" and right in (0, 1))
        ):
            self.add_message("redundant-arithmetic", node=node, args=(node.as_string(),))

    def _check_augmentable(self, node: Union[nodes.Assign, nodes.AnnAssign]) -> None:
        IMMUTABLE_OPS = ("/", "//", "%", "**", "<<", ">>")

        def add_message(target: str, param: nodes.BinOp) -> None:
            self.add_message(
                "use-augmented-assign",
                node=node,
                args=(target, node.value.op, param.as_string()),
            )

        def is_immutable(node: nodes.NodeNG) -> bool:
            if isinstance(node, (nodes.Const)) and isinstance(
                node.value, (int, float, bool, str, bytes, tuple)
            ):
                return True
            if isinstance(node, nodes.BinOp):
                return (
                    node.op in IMMUTABLE_OPS or is_immutable(node.left) or is_immutable(node.right)
                )
            if isinstance(node, nodes.Call):
                return any(
                    node.func.as_string().endswith(n)
                    for n in (
                        "int",
                        "float",
                        "bool",
                        "str",
                        "bytes",
                        "tuple",
                        "len",
                        "sum",
                        "chr",
                        "ord",
                        "trunc",
                        "round",
                        "sqrt",
                        "cos",
                        "sin",
                        "radians",
                        "degrees",
                    )
                )
            if isinstance(node, nodes.IfExp):
                return is_immutable(node.body) or is_immutable(node.orelse)
            return False

        if not isinstance(node.value, nodes.BinOp):
            return
        bin_op = node.value

        if isinstance(node, nodes.Assign):
            target = node.targets[0].as_string()
        elif isinstance(node, nodes.AnnAssign):
            target = node.target.as_string()
        else:
            assert False, "unreachable"

        left_value = infer_to_value(bin_op.left)
        right_value = infer_to_value(bin_op.right)

        if node.value.op in IMMUTABLE_OPS or is_immutable(left_value) or is_immutable(right_value):
            if target == bin_op.left.as_string():
                add_message(target, bin_op.right)
            elif bin_op.op in "+*|&" and target == bin_op.right.as_string():
                if not isinstance(left_value, nodes.Const) or not isinstance(
                    left_value.value, (str, bytes, tuple)
                ):
                    add_message(target, bin_op.left)

    def _check_multiplied_list(self, node: nodes.BinOp) -> None:
        def is_mutable(elem: nodes.NodeNG) -> bool:
            return type(elem) in (nodes.List, nodes.Set, nodes.Dict) or (
                isinstance(elem, nodes.Call)
                and isinstance(elem.func, nodes.Name)
                and elem.func.name in ("list", "set", "dict")
            )

        if node.op != "*" or (
            not isinstance(node.left, nodes.List) and not isinstance(node.right, nodes.List)
        ):
            return

        assert not isinstance(node.left, nodes.List) or not isinstance(node.right, nodes.List)
        lst = node.left if isinstance(node.left, nodes.List) else node.right

        if any(is_mutable(elem) for elem in lst.elts):
            self.add_message("do-not-multiply-mutable", node=node)

    def _check_redundant_elif(self, node: nodes.If) -> None:
        if_test = node.test
        if node.has_elif_block():
            next_if = node.orelse[0]
        # TODO report another message (may be FP)
        # elif isinstance(node.next_sibling(), nodes.If) and len(node.next_sibling().orelse) == 0:
        #     next_if = node.next_sibling()
        else:
            return

        if is_negation(if_test, next_if.test, negated_rt=False):
            self.add_message("redundant-elif", node=next_if)
            if (
                node.has_elif_block()
                and next_if == node.orelse[0]
                and len(node.orelse[0].orelse) > 0
            ):
                self.add_message("unreachable-else", node=node.orelse[0].orelse[0])

    def _check_no_is(self, node: nodes.Compare) -> None:
        for i, (op, val) in enumerate(node.ops):
            if (
                op in ("is", "is not")
                and isinstance(val, nodes.Const)
                and isinstance(val.value, bool)
            ):
                prev_val = node.ops[i - 1][1] if i > 0 else node.left
                negate = (op == "is") != val.value
                self.add_message(
                    "no-is-bool",
                    node=node,
                    args=(
                        f"{'not ' if negate else ''}{prev_val.as_string()}",
                        f"{prev_val.as_string()} {op} {val.as_string()}",
                    ),
                )

    def _is_ord(self, node: nodes.NodeNG) -> bool:
        return isinstance(node, nodes.Call) and node.func.as_string() == "ord"

    def _contains_ord(self, node: nodes.NodeNG) -> bool:
        if self._is_ord(node):
            return True
        if isinstance(node, nodes.BinOp):
            return self._is_ord(node.left) or self._is_ord(node.right)
        return False

    def _is_preffered(self, value: int) -> bool:
        return chr(value) in "azAZ09"

    def _in_suggestable_range(self, value: int) -> bool:
        return ord(" ") <= value < 127  # chr(127) is weird

    def _check_use_ord_letter(self, node: nodes.BinOp) -> None:
        def add_message(param: nodes.NodeNG, value: int, suggestion: str) -> None:
            self.add_message("use-ord-letter", node=param, args=(suggestion, value))

        if node.op not in ("+", "-"):
            return

        for ord_param, const_param in ((node.left, node.right), (node.right, node.left)):
            value = get_const_value(const_param)
            if (
                value is None
                or not isinstance(value, int)
                or not self._in_suggestable_range(value)
                or not self._contains_ord(ord_param)
            ):
                continue

            if self._is_preffered(value + 1):
                suggestion = f"ord('{chr(value + 1)}') - 1"
            elif self._is_preffered(value - 1):
                suggestion = f"ord('{chr(value - 1)}') + 1"
            elif not isinstance(ord_param, nodes.BinOp) or self._is_preffered(value):
                suggestion = f"ord('{chr(value)}')"
            else:
                continue

            if (node.op == "-" and const_param == node.right and suggestion.endswith("+ 1")) or (
                node.op == "+" and const_param == node.left and suggestion.endswith("- 1")
            ):
                add_message(const_param, value, f"({suggestion})")
            else:
                add_message(const_param, value, suggestion)

    def _check_magical_constant_in_ord_compare(self, node: nodes.Compare) -> None:
        def add_message(param: nodes.NodeNG, value: int, suggestion: str) -> None:
            self.add_message("use-literal-letter", node=param, args=(suggestion, value))

        def change(op: str) -> str:
            if op == "<":
                return "<="
            if op == "<=":
                return "<"
            if op == ">":
                return ">="
            if op == ">=":
                return ">"
            assert False, "unreachable"

        all_ops = [(None, node.left)] + node.ops
        contains_ord = [self._contains_ord(param) for _, param in all_ops]

        if not any(contains_ord):
            return

        for i, (op, param) in enumerate([(None, node.left), node.ops[-1]]):
            value = get_const_value(param)
            if value is None or not self._in_suggestable_range(value):
                continue

            if i == 0:
                op, other = node.ops[0]
                if self._is_preffered(value + 1) and op in ("<", ">="):
                    add_message(param, value, f"'{chr(value + 1)}' {change(op)}")
                elif self._is_preffered(value - 1) and op in (">", "<="):
                    add_message(param, value, f"'{chr(value - 1)}' {change(op)}")
                elif (
                    not contains_ord[1]
                    or not isinstance(other, nodes.BinOp)
                    or self._is_preffered(value)
                ):
                    add_message(param, value, f"'{chr(value)}' {op}")
            else:
                if self._is_preffered(value + 1) and op in (">", "<="):
                    add_message(param, value, f"{change(op)} '{chr(value + 1)}'")
                elif self._is_preffered(value - 1) and op in ("<", ">="):
                    add_message(param, value, f"{change(op)} '{chr(value - 1)}'")
                elif (
                    not contains_ord[-2]
                    or not isinstance(all_ops[-2][1], nodes.BinOp)
                    or self._is_preffered(value)
                ):
                    add_message(param, value, f"{op} '{chr(value)}'")

    def _check_use_early_return(self, node: nodes.If):
        def ends_block(node: nodes.NodeNG) -> bool:
            if isinstance(node, nodes.If):
                return (
                    ends_block(node.body[-1])
                    and len(node.orelse) > 0
                    and ends_block(node.orelse[-1])
                )
            return isinstance(node, (nodes.Return, nodes.Break, nodes.Continue))

        if is_parents_elif(node):
            return

        if len(node.orelse) > 0:
            if get_statements_count(node.orelse, include_defs=True, include_name_main=True) > 2:
                return
            last = node.orelse[-1]
        elif ends_block(node.body[-1]):
            last = node.next_sibling()
        else:
            return

        if (
            ends_block(last)
            and get_statements_count(node.body, include_defs=True, include_name_main=True) > 3
        ):
            self.add_message("use-early-return", node=node)

    SWITCHED_COMPARATOR = {
        ">=": "<=",
        ">": "<",
        "<=": ">=",
        "<": ">",
    }

    def _get_values_and_comparator(
        self, node: nodes.Compare
    ) -> Tuple[nodes.NodeNG, str, nodes.NodeNG]:
        """
        This method assumes node is a comparison between just two values.
        """
        left, (comp, right) = node.left, node.ops[0]
        return left, comp, right

    def _is_constant(self, node: nodes.NodeNG) -> bool:
        return get_const_value(node) is not None

    def _is_numeric(self, node: nodes.NodeNG) -> bool:
        value = get_const_value(node)
        return isinstance(value, int) or isinstance(value, float)

    def _get_node_comparator_const_value(
        self, node: nodes.NodeNG
    ) -> Optional[Tuple[Union[nodes.Call, nodes.Name], str, Any]]:
        """
        Assumes that node is a child of Bool Op.
        If the extraction was not successful returns None.
        It is succesful if and only if it is an inequality between
        a constant and a variable or a call to pure builtin function.

        When returns non None, the constant is last.
        """
        if not isinstance(node, nodes.Compare) or len(node.ops) >= 2:
            return None

        left, comp, right = self._get_values_and_comparator(node)

        left_is_constant = self._is_constant(left)
        right_is_constant = self._is_constant(right)

        if (
            (left_is_constant and right_is_constant)
            or (not left_is_constant and not right_is_constant)
            or comp not in self.SWITCHED_COMPARATOR
        ):
            return None

        if left_is_constant:
            left, comp, right = right, self.SWITCHED_COMPARATOR[comp], left

        if not (
            (isinstance(left, nodes.Call) and is_pure_builtin(left.func))
            or isinstance(left, nodes.Name)
        ) or not self._is_numeric(right):
            return None

        return left, comp, get_const_value(right)

    def _same_var_or_function_call(
        self, ex1: Union[nodes.Call, nodes.Name], ex2: Union[nodes.Call, nodes.Name]
    ) -> bool:
        """
        Note that the function has to be called on exactly 1 argument or the
        function returns False.
        """
        return type(ex1) == type(ex2) and (
            (isinstance(ex1, nodes.Name) and ex1.name == ex2.name)
            or (
                len(ex1.args) == len(ex2.args) == 1
                and isinstance(ex1.args[0], nodes.Name)
                and isinstance(ex2.args[0], nodes.Name)
                and ex1.args[0].name == ex2.args[0].name
                and ex1.func.as_string() == ex2.func.as_string()
            )
        )

    def _get_comparator_by_restriction(self, cmp1: str, cmp2: str, more_restrictive: bool) -> str:
        if len(cmp1) > len(cmp2):
            cmp1, cmp2 = cmp2, cmp1

        return cmp1 if more_restrictive else cmp2

    def _remove_redundant_compare(
        self, cmp1: str, const1: Any, cmp2: str, const2: Any, is_and: bool
    ) -> str:
        """
        Supposes that cmp1 and cmp2 are comparisons in the same direction (i.e. > and >=, ...)
        and that const1 and const2 are both numric values.

        <is_and> is True when there is <and> operation between the two comparisons and
        is False when there is <or> between them.
        """
        if const1 == const2:
            return self._get_comparator_by_restriction(cmp1, cmp2, is_and) + " " + str(const1)

        # make the const1 smaller than const2
        if const1 > const2:
            cmp1, const1, cmp2, const2 = cmp2, const2, cmp1, const1

        if cmp1 == ">" or cmp1 == ">=":
            if is_and:
                return cmp2 + " " + str(const2)
            return cmp1 + " " + str(const1)

        if is_and:
            return cmp1 + " " + str(const1)

        return cmp2 + " " + str(const2)

    def _check_for_simplification_of_single_or(self, node: nodes.BoolOp) -> None:
        """
        Assumes that node is a BoolOp representation of 'and' operator
        and that it is just a binary operator (ie not: a or b or c).
        Checks for problems like 'f(x) >= 4 or f(x) <= -4' and suggests to
        replace them with 'abs(f(x)) >= 4'. (f is pure builtin function or
        identity)
        """
        if node.op != "or" or len(node.values) != 2:
            return

        operand1 = self._get_node_comparator_const_value(node.values[0])
        operand2 = self._get_node_comparator_const_value(node.values[1])

        if not operand1 or not operand2:
            return

        expr1, cmp1, const1 = operand1
        expr2, cmp2, const2 = operand2

        if not self._same_var_or_function_call(expr1, expr2):
            return

        expr_string = expr1.as_string()

        if cmp1[0] == cmp2[0]:
            new_expr = (
                expr_string
                + " "
                + self._remove_redundant_compare(cmp1, const1, cmp2, const2, False)
            )

            self.add_message(
                "redundant-compare-in-condition",
                node=node,
                args=(get_name(node), new_expr),
            )
            return

        if const1 != -const2 or cmp1 != self.SWITCHED_COMPARATOR[cmp2]:
            return

        new_expr = "True"

        if const1 == 0:
            if cmp1 in {"<", ">"}:
                new_expr = expr_string + " != 0"
            # Note that this case belongs to simplifiable-single-or-with-abs,
            # but is a bit different. (suggests x != 0)

        elif cmp1 in {">=", ">"}:
            if const1 > 0:
                new_expr = "abs(" + expr_string + ") " + cmp1 + " " + str(const1)
        else:
            if const1 < 0:
                new_expr = "abs(" + expr_string + ") " + cmp2 + " " + str(const2)

        self.add_message(
            "simplifiable-single-or-with-abs",
            node=node,
            args=(get_name(node), new_expr),
        )

    def _check_for_simplification_of_single_and(self, node: nodes.BoolOp) -> None:
        """
        Assumes that node is a BoolOp representation of 'and' operator
        and that it is just a binary operator (ie not: a and b and c).
        Checks for problems like 'f(x) < 4 or f(x) > -4' and suggests to
        replace them with 'abs(f(x)) < 4'. (f is pure builtin function or
        identity)
        """
        if node.op != "and" or len(node.values) != 2:
            return

        operand1 = self._get_node_comparator_const_value(node.values[0])
        operand2 = self._get_node_comparator_const_value(node.values[1])

        if not operand1 or not operand2:
            return

        expr1, cmp1, const1 = operand1
        expr2, cmp2, const2 = operand2

        if not self._same_var_or_function_call(expr1, expr2):
            return

        expr_string = expr1.as_string()

        if cmp1[0] == cmp2[0]:
            new_expr = (
                expr_string + " " + self._remove_redundant_compare(cmp1, const1, cmp2, const2, True)
            )

            self.add_message(
                "redundant-compare-in-condition",
                node=node,
                args=(new_expr),
            )
            return

        if const1 != -const2 or cmp1 != self.SWITCHED_COMPARATOR[cmp2]:
            return

        new_expr = "False"

        if const1 == 0:
            if cmp1 in {"<=", ">="}:
                new_expr = expr_string + " == 0"
        elif cmp1 in {">=", ">"}:
            if const1 < 0:
                new_expr = "abs(" + expr_string + ") " + cmp2 + " " + str(const2)
        else:
            if const1 > 0:
                new_expr = "abs(" + expr_string + ") " + cmp1 + " " + str(const1)

        self.add_message(
            "simplifiable-single-and-with-abs",
            node=node,
            args=(new_expr),
        )

    def _check_for_simplification_of_and(self, node: nodes.BoolOp) -> None:
        if node.op != "and" or len(node.values) == 2:
            return

    def _check_for_simplification_of_or(self, node: nodes.BoolOp) -> None:
        if node.op != "or" or len(node.values) == 2:
            return

    @only_required_for_messages(
        "simplifiable-single-and-with-abs",
        "simplifiable-single-or-with-abs",
        "simplifiable-and-with-abs",
        "simplifiable-or-with-abs",
        "redundant-compare-in-condition",
    )
    def visit_boolop(self, node: nodes.BoolOp) -> None:
        self._check_for_simplification_of_single_or(node)
        self._check_for_simplification_of_single_and(node)
        self._check_for_simplification_of_or(node)
        self._check_for_simplification_of_and(node)

    @only_required_for_messages("use-append", "use-isdecimal", "use-integral-division")
    def visit_call(self, node: nodes.Call) -> None:
        self._check_extend(node)
        self._check_isdecimal(node)
        self._check_div(node)

    @only_required_for_messages("use-append", "redundant-arithmetic")
    def visit_augassign(self, node: nodes.AugAssign) -> None:
        self._check_augassign_extend(node)
        self._check_redundant_arithmetic(node)

    @only_required_for_messages("no-loop-else")
    def visit_while(self, node: nodes.While) -> None:
        self._check_loop_else(node.orelse, "while")

    @only_required_for_messages("no-loop-else", "at-most-one-iteration-for-loop")
    def visit_for(self, node: nodes.For) -> None:
        self._check_loop_else(node.orelse, "for")
        self._check_iteration_count(node)

    @only_required_for_messages("use-elif", "redundant-elif", "use-early-return")
    def visit_if(self, node: nodes.If) -> None:
        self._check_else_if(node)
        self._check_redundant_elif(node)
        self._check_use_early_return(node)

    @only_required_for_messages(
        "no-repeated-op", "redundant-arithmetic", "do-not-multiply-mutable", "use-ord-letter"
    )
    def visit_binop(self, node: nodes.BinOp) -> None:
        self._check_repeated_operation(node)
        self._check_redundant_arithmetic(node)
        self._check_multiplied_list(node)
        self._check_use_ord_letter(node)

    @only_required_for_messages("use-augmented-assign")
    def visit_assign(self, node: nodes.Assign) -> None:
        self._check_augmentable(node)

    @only_required_for_messages("use-augmented-assign")
    def visit_annassign(self, node: nodes.AnnAssign) -> None:
        self._check_augmentable(node)

    @only_required_for_messages("no-is-bool", "magical-constant-in-ord-compare")
    def visit_compare(self, node: nodes.Compare) -> None:
        self._check_no_is(node)
        self._check_magical_constant_in_ord_compare(node)


def register(linter: "PyLinter") -> None:
    """This required method auto registers the checker during initialization.
    :param linter: The linter to register the checker to.
    """
    linter.register_checker(Short(linter))
