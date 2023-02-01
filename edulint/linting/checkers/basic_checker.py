from astroid import nodes  # type: ignore
from typing import TYPE_CHECKING, Optional, List, Tuple, Union, TypeVar, Iterator, Dict, Set
import re

from pylint.checkers import BaseChecker  # type: ignore

if TYPE_CHECKING:
    from pylint.lint import PyLinter  # type: ignore

from edulint.linting.checkers.utils import \
    BaseVisitor, Named, get_name, get_assigned_to, is_any_assign, is_builtin, get_range_params, get_const_value


T = TypeVar("T")


class ModifiedListener(BaseVisitor[T]):

    NON_PURE_METHODS = re.compile(r"append|clear|extend|insert|pop|remove|reverse|sort|add|.*update|write")

    def __init__(self, watched: List[Named]):
        self.watched = watched
        self.modified = {get_name(var): [] for var in watched}
        self.stack = [{get_name(var): var.scope() for var in watched}]
        super().__init__()

    def _init_var_in_scope(self, node: nodes.NodeNG) -> T:
        self.stack[-1][get_name(node)] = node.scope()

    def visit_functiondef(self, node: nodes.FunctionDef) -> T:
        self.stack.append({})
        for arg in node.args.args:
            self._init_var_in_scope(arg)

        result = self.visit_many(node.get_children())

        self.stack.pop()
        return result

    def visit_global(self, node: nodes.Global) -> T:
        for name in node.names:
            self.stack[-1][name] = node.root().scope()

        return self.default

    def visit_nonlocal(self, node: nodes.Nonlocal) -> T:
        for name in node.names:
            self.stack[-1][name] = node.scope().parent.scope()

        return self.default

    def was_modified(self, node: nodes.NodeNG, allow_definition: bool) -> bool:
        return len(self.get_all_modifiers(node)) > (1 if allow_definition else 0)

    @staticmethod
    def _reassigns(node: nodes.NodeNG) -> bool:
        return type(node) in (nodes.AssignName, nodes.AssignAttr, nodes.DelName, nodes.DelAttr)

    def was_reassigned(self, node: nodes.NodeNG, allow_definition: bool) -> bool:
        return sum(self._reassigns(mod) for mod in self.get_all_modifiers(node)) > (1 if allow_definition else 0)

    def get_all_modifiers(self, node: nodes.NodeNG) -> List[nodes.NodeNG]:
        return self.modified[get_name(node)]

    def get_sure_modifiers(self, node: nodes.NodeNG) -> List[nodes.NodeNG]:
        result = []
        for modifier in self.get_all_modifiers(node):
            if ModifiedListener._reassigns(modifier):
                break
            result.append(modifier)
        return result

    @staticmethod
    def _strip(node: nodes.NodeNG) -> Optional[Union[nodes.Name, nodes.AssignName]]:
        while True:
            if isinstance(node, nodes.Subscript):
                node = node.value
            elif type(node) in (nodes.Attribute, nodes.AssignAttr, nodes.DelAttr):
                node = node.expr
            else:
                break

        return node if type(node) in (nodes.Name, nodes.AssignName, nodes.DelName) else None

    def _get_var_scope(self, var: str) -> Optional[Dict[str, nodes.NodeNG]]:
        for scope in reversed(self.stack):
            if var in scope:
                return scope
        return None

    def _is_same_var(self, var: Named, node: Named) -> bool:
        varname = get_name(var)
        return varname == get_name(node) and self._get_var_scope(varname)[varname] == var.scope()

    def _visit_assigned_to(self, node: nodes.NodeNG) -> None:
        stripped = self._strip(node)
        if stripped is None:
            return

        if isinstance(node, nodes.AssignName) and get_name(stripped) not in self.stack[-1]:
            self._init_var_in_scope(stripped)

        for var in self.watched:
            if self._is_same_var(var, stripped):
                self.modified[get_name(var)].append(node)

    def _names_from_tuple(self, targets: List[nodes.NodeNG]) -> Iterator[nodes.NodeNG]:
        for target in targets:
            if not isinstance(target, nodes.Tuple):
                yield target
            else:
                yield from self._names_from_tuple(target.elts)

    def visit_assign(self, assign: nodes.Assign) -> T:
        for target in self._names_from_tuple(assign.targets):
            self._visit_assigned_to(target)

        return self.visit_many(assign.get_children())

    def visit_augassign(self, node: nodes.AugAssign) -> T:
        self._visit_assigned_to(node.target)
        return self.visit_many(node.get_children())

    def visit_annassign(self, node: nodes.AnnAssign) -> T:
        self._visit_assigned_to(node.target)
        return self.visit_many(node.get_children())

    def visit_attribute(self, node: nodes.Attribute) -> T:
        if isinstance(node.parent, nodes.Call) \
                and ModifiedListener.NON_PURE_METHODS.match(node.attrname):

            stripped = self._strip(node)
            if stripped is None:
                return self.visit_many(node.get_children())

            for var in self.watched:
                if self._is_same_var(var, stripped):
                    self.modified[get_name(var)].append(node.parent)

        return self.visit_many(node.get_children())

    def visit_del(self, node: nodes.Delete) -> T:
        for target in node.targets:
            if isinstance(target, nodes.DelName):
                scope = self._get_var_scope(target.name)
                if scope is not None:
                    scope.pop(target.name)

            stripped = self._strip(target)

            for var in self.watched:
                if self._is_same_var(var, stripped):
                    self.modified[get_name(var)].append(
                        target if type(target) in (nodes.DelName, nodes.DelAttr) else node
                    )

        return self.visit_many(node.get_children())

    def visit_for(self, node: nodes.For) -> T:
        self._visit_assigned_to(node.target)
        return self.visit_many(node.body)


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
            "Emitted when the boundaries of a range can be made tighter."
        ),
        "R6303": (
            "Iterated structure %s is being modified inside the for loop body. Use while loop or iterate over a copy.",
            "modifying-iterated-structure",
            "Emitted when the structure that is being iterated over is being modified in the for loops body."
        ),
        "R6304": (
            "Changing the control variable %s of a for loop has no effect.",
            "changing-control-variable",
            "Emitted when the control variable of a for loop is being changed."
        ),
        "R6305": (
            "Use for loop.",
            "use-for-loop",
            "Emitted when a while loop can be transformed into a for loop."
        ),
        "R6306": (
            "Inner for loop shadows outer for loop's control variable %s.",
            "loop-shadows-control-variable",
            "Emitted when a for loop shadows control variable of an outer for loop."
        )
    }

    def _check_no_while_true(self, node: nodes.While) -> None:
        if not isinstance(node.test, nodes.Const) or not node.test.bool_value():
            return

        first = node.body[0]
        if isinstance(first, nodes.If) and isinstance(first.body[-1], nodes.Break):
            self.add_message("no-while-true", node=node, args=(first.test.as_string()))

    def _check_use_for_loop(self, node: nodes.While) -> None:
        def get_relevant_vals(node: nodes.NodeNG, result: Set[nodes.NodeNG] = None) -> Tuple[bool, Set[nodes.NodeNG]]:
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
            if isinstance(node, nodes.Call) and node.func.as_string() == "len" and len(node.args) == 1:
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
                return binop.op in ("+", "-") \
                    and ((binop.left.as_string() == node.as_string() and get_const_value(binop.right) == 1)
                         or (binop.right.as_string() == node.as_string() and get_const_value(binop.left) == 1))
            return False

        test = node.test
        if not isinstance(test, nodes.Compare) or len(test.ops) != 1 or test.ops[0][0] not in ("<", "<=", ">", ">="):
            return

        lt, rt = test.left, test.ops[0][1]
        lt_decomposable, lt_vals = get_relevant_vals(lt)
        rt_decomposable, rt_vals = get_relevant_vals(rt)
        if not lt_decomposable or not rt_decomposable:
            return

        all_vals = lt_vals | rt_vals
        listener = ModifiedListener(all_vals)
        listener.visit_many(node.body)

        all_modifiers = [(val in lt_vals, listener.get_all_modifiers(val)) for val in all_vals]
        nonempty_modifiers = [(from_lt, modifiers) for (from_lt, modifiers) in all_modifiers if len(modifiers) > 0]

        if len(nonempty_modifiers) != 1:
            return

        from_lt, only_modifiers = nonempty_modifiers[0]
        if len(only_modifiers) != 1:
            return

        only_modifier = only_modifiers[0]

        if self._get_block_line(only_modifier).parent != node or not adds_or_subtracts_one(only_modifier) \
                or (only_modifier.as_string() != lt.as_string() and only_modifier.as_string() != rt.as_string()):
            return

        self.add_message("use-for-loop", node=node)

    def visit_while(self, node: nodes.While) -> None:
        self._check_no_while_true(node)
        self._check_use_for_loop(node)

    def _check_use_tighter_bounds(self, node: nodes.For) -> None:
        def compares_equality(node: nodes.NodeNG) -> bool:
            return isinstance(node, nodes.Compare) and len(node.ops) == 1 and node.ops[0][0] == "=="

        def compares_to_start(node: nodes.Compare, var: str, start: nodes.NodeNG) -> bool:
            left, (_, right) = node.left, node.ops[0]
            left, right = left.as_string(), right.as_string()
            return (left == var and right == start.as_string()) or (left == start.as_string() and right == var)

        def is_last_before_end(node: nodes.NodeNG, stop: nodes.NodeNG, step: nodes.NodeNG) -> bool:
            const_node = get_const_value(node)
            const_stop = get_const_value(stop)
            const_step = get_const_value(step)
            return (isinstance(node, nodes.BinOp) and node.op == "-"
                    and node.left.as_string() == stop.as_string() and node.right.as_string() == step.as_string()) \
                or (isinstance(const_node, int) and isinstance(const_stop, int) and isinstance(const_step, int)
                    and const_node == const_stop - const_step)

        def compares_to_last_before_end(node: nodes.Compare, var: str, stop: nodes.NodeNG, step: nodes.NodeNG) -> bool:
            left, (_, right) = node.left, node.ops[0]
            return (left.as_string() == var and is_last_before_end(right, stop, step)) \
                or (is_last_before_end(left, stop, step) and right.as_string() == var)

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

            if compares_equality(test) and len(if_.body) == 1 and type(if_.body[-1]) in (nodes.Break, nodes.Continue):
                if compares_to_start(test, var, start):
                    self.add_message("use-tighter-boundaries", node=node, args=("first",))
                elif compares_to_last_before_end(test, var, stop, step):
                    self.add_message("use-tighter-boundaries", node=node, args=("last",))
            # TODO expand, tips: len(node.body) == 1, isinstance(if_.body[-1], nodes.Return), allow nodes in the middle,
            #                    allow longer bodies

    @staticmethod
    def _get_block_line(node: nodes.NodeNG):
        while not isinstance(node, nodes.Statement):
            node = node.parent
        return node

    @staticmethod
    def _get_last_block_line(node: nodes.NodeNG):
        node = ImproperLoop._get_block_line(node)

        while node.next_sibling() is not None:
            node = node.next_sibling()
        return node

    def _check_modifying_iterable(self, node: nodes.For) -> None:
        iterated = node.iter
        if type(iterated) not in (nodes.Name, nodes.Attribute):  # TODO allow any node type
            return

        listener = ModifiedListener({iterated})
        listener.visit_many(node.body)

        for modifier in listener.get_sure_modifiers(iterated):
            if isinstance(modifier, nodes.Call) \
                    and type(self._get_last_block_line(modifier)) not in (nodes.Break, nodes.Return):
                self.add_message("modifying-iterated-structure", node=modifier, args=(get_name(iterated),))

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
        listener = ModifiedListener({control_var})
        listener.visit_many(node.body)

        for modifier in listener.get_all_modifiers(control_var):
            mod_statement = self._get_block_line(modifier)
            if isinstance(mod_statement, nodes.For) and mod_statement.target.as_string() == control_var.as_string() \
                    and control_var.as_string() != "_":
                self.add_message("loop-shadows-control-variable", node=mod_statement, args=(modifier.as_string()))
            if is_last_block(mod_statement, node):
                self.add_message("changing-control-variable", node=mod_statement, args=(control_var.as_string(),))

    def visit_for(self, node: nodes.For) -> None:
        self._check_use_tighter_bounds(node)
        self._check_modifying_iterable(node)
        self._check_control_variable_changes(node)


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
    linter.register_checker(ImproperLoop(linter))
    linter.register_checker(NoGlobalVars(linter))
