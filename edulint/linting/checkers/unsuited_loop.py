from astroid import nodes, Context  # type: ignore
from functools import reduce
from typing import TYPE_CHECKING, List, Iterator, Tuple, Optional

from pylint.checkers import BaseChecker  # type: ignore
from pylint.checkers.utils import only_required_for_messages

if TYPE_CHECKING:
    from pylint.lint import PyLinter  # type: ignore

from edulint.linting.checkers.utils import (
    get_range_params,
    get_const_value,
    is_builtin,
    requires_data_dependency_analysis,
)
from edulint.linting.analyses.cfg.utils import successors_from_loc, get_cfg_loc, CFGLoc
from edulint.linting.analyses.var_events import VarEventType, Variable, VarEvent, strip_to_name
from edulint.linting.analyses.data_dependency import (
    vars_in,
    node_to_var,
    MODIFYING_EVENTS,
    get_events_for,
    get_events_by_var,
    filter_events_for,
)


class UnsuitedLoop(BaseChecker):
    name = "unsuited-loop"
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
            "You should use for loop instead of this form of while loop.",
            "use-for-loop",
            "Emitted when a while loop can be transformed into a for loop.",
        ),
        "R6306": (
            "Inner for loop shadows outer for loop's control variable %s.",
            "loop-shadows-control-variable",
            "Emitted when a for loop shadows control variable of an outer for loop.",
        ),
        "R6307": (
            'Iterate directly: "for var in %s" (with appropriate name for "var")',
            "use-foreach",
            "Emitted when a for-range loop is used while a for-each loop would suffice.",
            {"old_names": [("R6101", "old-use-foreach")]},
        ),
        "R6308": (
            'Iterate using enumerate: "for %s, var in enumerate(%s)" (with appropriate name for "var")',
            "use-enumerate",
            "Emitted when a for-range loop is used with the element at each index is accessed as well.",
            {"old_names": [("R6102", "old-use-enumerate")]},
        ),
    }

    def _check_no_while_true(self, node: nodes.While) -> None:
        if not isinstance(node.test, nodes.Const) or not node.test.bool_value():
            return

        first = node.body[0]
        if isinstance(first, nodes.If) and isinstance(first.body[-1], nodes.Break):
            self.add_message("no-while-true", node=node, args=(first.test.as_string(),))

    @requires_data_dependency_analysis
    def _check_use_for_loop(self, node: nodes.While) -> None:
        # TODO allow different increments?
        def get_change_value(node: nodes.NodeNG) -> Optional[int]:
            if not isinstance(node, nodes.AssignName):
                return None

            expr = node.parent
            const = None
            op = None
            if isinstance(expr, nodes.AugAssign) and expr.op in ("+=", "-="):
                const = get_const_value(expr.value)
                op = expr.op[0]
            if isinstance(expr, nodes.Assign) and isinstance(expr.value, nodes.BinOp):
                binop = expr.value
                if binop.op in ("+", "-"):
                    op = binop.op
                    if binop.left.as_string() == node.as_string():
                        const = get_const_value(binop.right)
                    if binop.right.as_string() == node.as_string():
                        const = get_const_value(binop.left)
            if const is None:
                return None

            return const if op == "+" else -const

        def var_can_be_from_range(var: Variable, test: nodes.NodeNG) -> bool:
            events = list(get_events_for([var], [test]))
            return len(events) == 1 and events[0].node.parent == test

        def stop_on_event_node_wrap(events):
            event_nodes = {get_cfg_loc(e.node).node for e in events}

            def stop_on(loc: CFGLoc):
                return (
                    loc is None
                    or isinstance(loc.node, (nodes.Break, nodes.Return))
                    or loc.node in event_nodes
                )

            return stop_on

        def event_on_every_path(node: nodes.While, events):
            if node.next_sibling() is None:
                node.cfg_loc.block.locs.append(None)

            result = True
            for loc in successors_from_loc(
                node.body[0].cfg_loc,
                stop_on_loc=stop_on_event_node_wrap(events),
                include_start=True,
                include_end=True,
                explore_functions=True,
                explore_classes=True,
            ):
                if (
                    loc is None
                    or node not in loc.node.node_ancestors()
                    or (
                        isinstance(loc.node, (nodes.Break, nodes.Return))
                        and any(
                            node not in use.node.node_ancestors()
                            for event in events
                            for use in event.uses
                        )
                    )
                ):
                    result = False
                    break
            if node.cfg_loc.block.locs[-1] is None:
                node.cfg_loc.block.locs.pop()

            return result

        def event_in_loop(parent_loop: nodes.While, event):
            parent = event.node
            while parent != parent_loop:
                if isinstance(parent, (nodes.For, nodes.While)):
                    return True
                parent = parent.parent
            return False

        def modification_after_modification(events):
            return any(e.uses != events[0].uses for e in events)

        def changes_towards_limit(test, only_var, change):
            lt, (op, rt) = test.left, test.ops[0]
            if only_var in vars_in(lt):
                return change > 0 and op in ("<", "<=") or change < 0 and op in (">", ">=")
            assert only_var in vars_in(rt)
            return change < 0 and op in ("<", "<=") or change > 0 and op in (">", ">=")

        test = node.test
        if (
            not isinstance(test, nodes.Compare)
            or len(test.ops) != 1
            or test.ops[0][0] not in ("<", "<=", ">", ">=")
        ):
            return

        test_vars = list(vars_in(test).keys())
        if len(test_vars) == 0:
            return

        events_by_var = get_events_by_var(test_vars, node.body, MODIFYING_EVENTS)

        if len(events_by_var) != 1:
            return

        only_var, events = next(iter(events_by_var.items()))
        change = reduce(
            lambda r, c: c if c is not None and r is not None and c == r else None,
            [get_change_value(e.node) for e in events],
        )
        if change not in (1, -1):
            return

        if (
            var_can_be_from_range(only_var, test)
            and changes_towards_limit(test, only_var, change)
            and not modification_after_modification(events)
            and not any(event_in_loop(node, e) for e in events)
            and event_on_every_path(node, events)
        ):
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
        while not node.is_statement:
            node = node.parent
        return node

    @staticmethod
    def _get_last_block_line(node: nodes.NodeNG) -> nodes.NodeNG:
        node = UnsuitedLoop._get_block_line(node)

        while node.next_sibling() is not None:
            node = node.next_sibling()
        return node

    @requires_data_dependency_analysis
    def _check_modifying_iterable(self, node: nodes.For) -> None:
        iterated = node.iter
        if not isinstance(iterated, nodes.Name):  # TODO allow any node type
            return

        iterated_var = node_to_var(iterated)
        if iterated_var is None:
            return

        # TODO reassigning iterated structure message?
        for event in get_events_for([iterated_var], node.body, MODIFYING_EVENTS):
            if (
                event.type in (VarEventType.ASSIGN, VarEventType.REASSIGN)
                and get_cfg_loc(event.node).node.parent == node
            ):
                break
            if (
                event.type == VarEventType.MODIFY
                and event.is_direct_modify()
                and not isinstance(
                    self._get_last_block_line(event.node), (nodes.Break, nodes.Return)
                )
            ):
                self.add_message(
                    "modifying-iterated-structure", node=event.node.parent, args=iterated_var.name
                )

    @requires_data_dependency_analysis
    def _check_control_variable_changes(self, node: nodes.For) -> None:
        range_params = get_range_params(node.iter)
        if range_params is None or not isinstance(node.target, nodes.AssignName):
            return

        control_var = node_to_var(node.target)
        assert control_var is not None
        if control_var.name.startswith("_"):
            return

        for event in get_events_for([control_var], node.body, MODIFYING_EVENTS):
            if isinstance(event.node.parent, nodes.For) and event.node == event.node.parent.target:
                self.add_message(
                    "loop-shadows-control-variable", node=event.node, args=control_var.name
                )
                continue

            if len(event.uses) == 0:
                self.add_message(
                    "changing-control-variable", node=event.node.parent, args=(control_var.name)
                )

    @requires_data_dependency_analysis
    def _check_improve_for_loop(self, node: nodes.For) -> None:
        def is_for_range_len(node: nodes.For) -> Tuple[bool, nodes.NodeNG]:
            range_params = get_range_params(node.iter)
            if range_params is None:
                return False, None

            start, stop, step = range_params
            return (
                isinstance(start, nodes.Const)
                and start.value == 0
                and isinstance(stop, nodes.Call)
                and is_builtin(stop.func, "len")
                and len(stop.args) == 1
                and isinstance(step, nodes.Const)
                and step.value == 1
            ), stop

        def get_indexing_events(structure_events: List[VarEvent]) -> List[VarEvent]:
            return [
                e
                for e in structure_events
                if isinstance(e.node.parent, nodes.Subscript) and e.node == e.node.parent.value
            ]

        def is_structure_indexed_just_by(
            index_var: Variable, indexing_events: List[VarEvent]
        ) -> bool:
            for event in indexing_events:
                slice_ = event.node.parent.slice
                if not isinstance(slice_, nodes.Name) or slice_.name != index_var.name:
                    return False
            return True

        def is_structure_assigned_into(structure_events: List[VarEvent]) -> bool:
            return any(
                e.type != VarEventType.READ
                and not isinstance(
                    e.node.parent.parent, (nodes.Subscript, nodes.Attribute, nodes.Call)
                )
                for e in structure_events
            )

        def is_structure_directly_modified(structure_events: List[VarEvent]) -> bool:
            return any(
                (
                    (e.type == VarEventType.MODIFY and e.is_direct_modify())
                    or (e.type not in (VarEventType.READ, VarEventType.MODIFY))
                )
                and not isinstance(self._get_last_block_line(e.node), (nodes.Break, nodes.Return))
                for e in structure_events
            )

        def is_structure_read(indexing_events: List[VarEvent]) -> bool:
            return any(e.node.parent.ctx == Context.Load for e in indexing_events)

        def is_index_modified(index_events: List[VarEvent]) -> bool:
            return any(e.type != VarEventType.READ for e in index_events)

        def is_index_used_just_for(structure: nodes.NodeNG, index_events: List[VarEvent]) -> bool:
            for event in index_events:
                if (
                    isinstance(event.node.parent, nodes.Subscript)
                    and event.node == event.node.parent.slice
                    # TODO use vars_in for next test
                    and event.node.parent.value.as_string() != structure.as_string()
                ):
                    return False
            return True

        def is_index_used_outside_subscript(
            index_events: List[VarEvent], structure: nodes.NodeNG
        ) -> bool:
            for event in index_events:
                if (
                    not isinstance(event.node.parent, nodes.Subscript)
                    or event.node != event.node.parent.slice
                    or event.node.parent.value.as_string() != structure.as_string()
                ):
                    return True
            return False

        is_, stop = is_for_range_len(node)
        if not is_:
            return

        structure = stop.args[0]
        if not isinstance(structure, (nodes.Name, nodes.Attribute, nodes.Subscript)):
            return

        stripped = strip_to_name(structure)
        if stripped is None:
            return

        structure_var = node_to_var(stripped)
        index_var = node_to_var(node.target)
        if structure_var is None or index_var is None:
            return

        events_by_var = get_events_by_var([structure_var, index_var], node.body)
        events_by_var[structure_var] = filter_events_for(structure, events_by_var[structure_var])

        indexing_events = get_indexing_events(events_by_var[structure_var])
        if (
            not is_structure_read(indexing_events)
            or not is_structure_indexed_just_by(index_var, indexing_events)
            or not is_index_used_just_for(structure, events_by_var[index_var])
            or is_index_modified(events_by_var[index_var])
            or is_structure_directly_modified(events_by_var[structure_var])
            or is_structure_assigned_into(events_by_var[structure_var])
        ):
            return

        if is_index_used_outside_subscript(events_by_var[index_var], structure):
            self.add_message("use-enumerate", args=(index_var.name, structure_var.name), node=node)
        else:
            self.add_message("use-foreach", args=structure_var.name, node=node)

    @only_required_for_messages(
        "use-tighter-boundaries",
        "modifying-iterated-structure",
        "changing-control-variable",
        "loop-shadows-control-variable",
        "use-enumerate",
        "use-foreach",
    )
    def visit_for(self, node: nodes.For) -> None:
        self._check_use_tighter_bounds(node)
        self._check_modifying_iterable(node)
        self._check_control_variable_changes(node)
        self._check_improve_for_loop(node)


def register(linter: "PyLinter") -> None:
    """This required method auto registers the checker during initialization.
    :param linter: The linter to register the checker to.
    """
    linter.register_checker(UnsuitedLoop(linter))
