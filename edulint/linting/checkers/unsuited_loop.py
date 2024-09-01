from astroid import nodes, Context  # type: ignore
from enum import Enum, auto
from functools import reduce
from typing import TYPE_CHECKING, List, Iterator, Union, Tuple

from pylint.checkers import BaseChecker  # type: ignore
from pylint.checkers.utils import only_required_for_messages

if TYPE_CHECKING:
    from pylint.lint import PyLinter  # type: ignore

from edulint.linting.checkers.utils import get_range_params, get_const_value, get_name, is_builtin
from edulint.linting.analyses.cfg.utils import successors_from_loc, get_cfg_loc, CFGLoc
from edulint.linting.checkers.modified_listener import ModifiedListener
from edulint.linting.analyses.var_events import VarEventType, Variable
from edulint.linting.analyses.data_dependency import (
    vars_in,
    node_to_var,
    MODIFYING_EVENTS,
    get_events_for,
    get_events_by_var,
)


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
            "Use for loop.",
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

    def _check_use_for_loop(self, node: nodes.While) -> None:
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
        if (
            var_can_be_from_range(only_var, test)
            and all(adds_or_subtracts_one(e.node) for e in events)
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

    def _check_modifying_iterable(self, node: nodes.For) -> None:
        iterated = node.iter
        if not isinstance(iterated, nodes.Name):  # TODO allow any node type
            return

        iterated_var = node_to_var(iterated)
        if iterated_var is None:
            return

        # TODO reassigning iterated structure?
        for event in get_events_for([iterated_var], node.body, (VarEventType.MODIFY,)):
            if isinstance(event.node.parent, nodes.Call) and not isinstance(
                self._get_last_block_line(event.node), (nodes.Break, nodes.Return)
            ):
                self.add_message(
                    "modifying-iterated-structure", node=event.node.parent, args=iterated_var.name
                )

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

    class StructureIndexedVisitor(ModifiedListener[Tuple[bool, bool]]):
        default = (False, False)

        def combine(self, results: List[Tuple[bool, bool]]) -> Tuple[bool, bool]:
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

        def combine(self, results: List[bool]) -> bool:
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

        def combine(self, results: List[UsesIndex]) -> UsesIndex:
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

    def _check_improve_for_loop(self, node: nodes.For) -> None:
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
