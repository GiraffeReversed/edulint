from astroid import nodes  # type: ignore
from typing import TYPE_CHECKING, List, Tuple, Iterator, Set, Optional

from pylint.checkers import BaseChecker  # type: ignore
from pylint.checkers.utils import only_required_for_messages

if TYPE_CHECKING:
    from pylint.lint import PyLinter  # type: ignore

from edulint.linting.checkers.utils import get_name, get_range_params, get_const_value
from edulint.linting.checkers.modified_listener import ModifiedListener


class ImproperLoop(BaseChecker):
    name = "improper-loop"
    msgs = {
        "R6301": (
            "The while condition can be replaced with '<negated %s>'",
            "no-while-true",
            "Emitted when the condition of a while loop is 'True' unnecessarily.",
        ),
        "R6302": (
            "Use tighter range boundaries, the %s iteration never happens.",
            "use-tighter-boundaries",
            "Emitted when the boundaries of a range can be made tighter.",
        ),
        "R6303": (
            "Iterated structure %s is being modified inside the for loop body. Use while loop or iterate over a copy.",
            "modifying-iterated-structure",
            "Emitted when the structure that is being iterated over is being modified in the for loops body.",
        ),
        "R6304": (
            "Changing the control variable %s of a for loop has no effect.",
            "changing-control-variable",
            "Emitted when the control variable of a for loop is being changed.",
        ),
        "R6305": (
            "Use for loop.",
            "use-for-loop",
            "Emitted when a while loop can be transformed into a for loop.",
        ),
        "R6306": (
            "Inner for loop shadows outer for loop's control variable %s.",
            "loop-shadows-control-variable",
            "Emitted when a for loop shadows control variable of an outer for loop.",
        ),
    }

    def _check_no_while_true(self, node: nodes.While) -> None:
        if not isinstance(node.test, nodes.Const) or not node.test.bool_value():
            return

        first = node.body[0]
        if isinstance(first, nodes.If) and isinstance(first.body[-1], nodes.Break):
            self.add_message("no-while-true", node=node, args=(first.test.as_string(),))

    def _check_use_for_loop(self, node: nodes.While) -> None:
        def get_relevant_vals(
            node: nodes.NodeNG, result: Optional[Set[nodes.NodeNG]] = None
        ) -> Tuple[bool, Set[nodes.NodeNG]]:
            result = result if result is not None else set()

            if isinstance(node, nodes.Const):
                return True, result
            if isinstance(node, nodes.Name):
                result.add(node)
                return True, result
            if isinstance(node, nodes.BinOp):
                v1 = get_relevant_vals(node.left, result)
                v2 = get_relevant_vals(node.right, result)
                return v1 and v2, result
            if (
                isinstance(node, nodes.Call)
                and node.func.as_string() == "len"
                and len(node.args) == 1
            ):
                return get_relevant_vals(node.args[0], result)
            return False, result

        # TODO allow different increments?
        def adds_or_subtracts_one(node: nodes.NodeNG) -> bool:
            if not isinstance(node, nodes.AssignName):
                return False

            expr = node.parent
            if isinstance(expr, nodes.AugAssign):
                return expr.op in ("+=", "-=") and get_const_value(expr.value) == 1
            if isinstance(expr, nodes.Assign) and isinstance(expr.value, nodes.BinOp):
                binop = expr.value
                return binop.op in ("+", "-") and (
                    (
                        binop.left.as_string() == node.as_string()
                        and get_const_value(binop.right) == 1
                    )
                    or (
                        binop.right.as_string() == node.as_string()
                        and get_const_value(binop.left) == 1
                    )
                )
            return False

        test = node.test
        if (
            not isinstance(test, nodes.Compare)
            or len(test.ops) != 1
            or test.ops[0][0] not in ("<", "<=", ">", ">=")
        ):
            return

        lt, rt = test.left, test.ops[0][1]
        lt_decomposable, lt_vals = get_relevant_vals(lt)
        rt_decomposable, rt_vals = get_relevant_vals(rt)
        if not lt_decomposable or not rt_decomposable:
            return

        all_vals = lt_vals | rt_vals
        listener: ModifiedListener[None] = ModifiedListener(list(all_vals))
        listener.visit_many(node.body)

        all_modifiers = [(val in lt_vals, listener.get_all_modifiers(val)) for val in all_vals]
        nonempty_modifiers = [
            (from_lt, modifiers) for (from_lt, modifiers) in all_modifiers if len(modifiers) > 0
        ]

        if len(nonempty_modifiers) != 1:
            return

        from_lt, only_modifiers = nonempty_modifiers[0]
        if len(only_modifiers) != 1:
            return

        only_modifier = only_modifiers[0]

        if (
            self._get_block_line(only_modifier).parent != node
            or not adds_or_subtracts_one(only_modifier)
            or (
                only_modifier.as_string() != lt.as_string()
                and only_modifier.as_string() != rt.as_string()
            )
        ):
            return

        self.add_message("use-for-loop", node=node)

    @only_required_for_messages("no-while-true", "use-for-loop")
    def visit_while(self, node: nodes.While) -> None:
        self._check_no_while_true(node)
        self._check_use_for_loop(node)

    def _check_use_tighter_bounds(self, node: nodes.For) -> None:
        def compares_equality(node: nodes.NodeNG) -> bool:
            return isinstance(node, nodes.Compare) and len(node.ops) == 1 and node.ops[0][0] == "=="

        def compares_to_start(node: nodes.Compare, var: str, start: nodes.NodeNG) -> bool:
            left, (_, right) = node.left, node.ops[0]
            left, right = left.as_string(), right.as_string()
            return (left == var and right == start.as_string()) or (
                left == start.as_string() and right == var
            )

        def is_last_before_end(node: nodes.NodeNG, stop: nodes.NodeNG, step: nodes.NodeNG) -> bool:
            const_node = get_const_value(node)
            const_stop = get_const_value(stop)
            const_step = get_const_value(step)
            return (
                isinstance(node, nodes.BinOp)
                and node.op == "-"
                and node.left.as_string() == stop.as_string()
                and node.right.as_string() == step.as_string()
            ) or (
                isinstance(const_node, int)
                and isinstance(const_stop, int)
                and isinstance(const_step, int)
                and const_node == const_stop - const_step
            )

        def compares_to_last_before_end(
            node: nodes.Compare, var: str, stop: nodes.NodeNG, step: nodes.NodeNG
        ) -> bool:
            left, (_, right) = node.left, node.ops[0]
            return (left.as_string() == var and is_last_before_end(right, stop, step)) or (
                is_last_before_end(left, stop, step) and right.as_string() == var
            )

        def relevant_nodes(body: List[nodes.NodeNG]) -> Iterator[nodes.If]:
            first = body[0]
            if isinstance(first, nodes.If):
                yield first
                while first.has_elif_block():
                    first = first.orelse[0]
                    yield first

            if len(body) > 1 and isinstance(body[-1], nodes.If):
                yield body[-1]

        range_params = get_range_params(node.iter)
        if range_params is None:
            return

        start, stop, step = range_params

        var = node.target.as_string()
        if isinstance(node.body[0], nodes.If):
            if_ = node.body[0]
            test = if_.test

            if (
                compares_equality(test)
                and len(if_.body) == 1
                and type(if_.body[-1]) in (nodes.Break, nodes.Continue)
            ):
                if compares_to_start(test, var, start):
                    self.add_message("use-tighter-boundaries", node=node, args=("first",))
                elif compares_to_last_before_end(test, var, stop, step):
                    self.add_message("use-tighter-boundaries", node=node, args=("last",))
            # TODO expand, tips: len(node.body) == 1, isinstance(if_.body[-1], nodes.Return), allow nodes in the middle,
            #                    allow longer bodies

    @staticmethod
    def _get_block_line(node: nodes.NodeNG) -> nodes.NodeNG:
        while not isinstance(node, nodes.Statement):
            node = node.parent
        return node

    @staticmethod
    def _get_last_block_line(node: nodes.NodeNG) -> nodes.NodeNG:
        node = ImproperLoop._get_block_line(node)

        while node.next_sibling() is not None:
            node = node.next_sibling()
        return node

    def _check_modifying_iterable(self, node: nodes.For) -> None:
        iterated = node.iter
        if type(iterated) not in (nodes.Name, nodes.Attribute):  # TODO allow any node type
            return

        listener: ModifiedListener[None] = ModifiedListener([iterated])
        listener.visit_many(node.body)

        for modifier in listener.get_sure_modifiers(iterated):
            if isinstance(modifier, nodes.Call) and type(
                self._get_last_block_line(modifier)
            ) not in (
                nodes.Break,
                nodes.Return,
            ):
                self.add_message(
                    "modifying-iterated-structure", node=modifier, args=(get_name(iterated),)
                )

    def _check_control_variable_changes(self, node: nodes.For) -> None:
        def is_last_block(node: nodes.NodeNG, for_: nodes.For) -> bool:
            stmt = self._get_block_line(node)
            while not isinstance(node, nodes.Module):
                if type(stmt) in (nodes.For, nodes.While):
                    return False
                if stmt == for_.body[-1]:
                    return True
                last_block_stmt = self._get_last_block_line(stmt)
                if stmt != last_block_stmt:
                    return False
                stmt = last_block_stmt.parent
            return False

        range_params = get_range_params(node.iter)
        if range_params is None:
            return

        control_var = node.target
        if control_var.as_string().startswith("_"):
            return

        listener: ModifiedListener[None] = ModifiedListener([control_var])
        listener.visit_many(node.body)

        for modifier in listener.get_all_modifiers(control_var):
            mod_statement = self._get_block_line(modifier)
            if (
                isinstance(mod_statement, nodes.For)
                and mod_statement.target.as_string() == control_var.as_string()
            ):
                self.add_message(
                    "loop-shadows-control-variable", node=mod_statement, args=(modifier.as_string())
                )
                continue
            if is_last_block(mod_statement, node):
                self.add_message(
                    "changing-control-variable", node=mod_statement, args=(control_var.as_string(),)
                )

    @only_required_for_messages(
        "use-tighter-boundaries",
        "modifying-iterated-structure",
        "changing-control-variable",
        "loop-shadows-control-variable",
    )
    def visit_for(self, node: nodes.For) -> None:
        self._check_use_tighter_bounds(node)
        self._check_modifying_iterable(node)
        self._check_control_variable_changes(node)


def register(linter: "PyLinter") -> None:
    """This required method auto registers the checker during initialization.
    :param linter: The linter to register the checker to.
    """
    linter.register_checker(ImproperLoop(linter))
