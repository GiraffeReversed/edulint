from astroid import nodes  # type: ignore
from typing import TYPE_CHECKING, Optional, List, Tuple, Union, TypeVar, Iterator
import re

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
        return len(self.modified[get_name(node)]) > (1 if allow_definition else 0)

    @staticmethod
    def _reassigns(node: nodes.NodeNG) -> bool:
        return type(node) in (nodes.AssignName, nodes.AssignAttr)

    def was_reassigned(self, node: nodes.NodeNG, allow_definition: bool) -> bool:
        return sum(self._reassigns(mod) for mod in self.get_modifiers(node)) > (1 if allow_definition else 0)

    def get_modifiers(self, node: nodes.NodeNG) -> List[nodes.NodeNG]:
        return self.modified[get_name(node)]

    @staticmethod
    def _is_assigned_to(node: Named) -> bool:
        return node in get_assigned_to(node.parent)

    @staticmethod
    def _strip(node: nodes.NodeNG) -> Optional[Union[nodes.Name, nodes.AssignName]]:
        while True:
            if isinstance(node, nodes.Subscript):
                node = node.value
            elif isinstance(node, nodes.Attribute) or isinstance(node, nodes.AssignAttr):
                node = node.expr
            else:
                break

        return node if isinstance(node, nodes.Name) or isinstance(node, nodes.AssignName) else None

    def _is_same_var(self, var: Named, node: Named) -> bool:
        varname = get_name(var)
        return varname == get_name(node) and \
            [sub[varname] for sub in reversed(self.stack) if varname in sub][0] == var.scope()

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


class NoWhileTrue(BaseChecker):

    name = "no-while-true"
    msgs = {
        "R6301": (
            "The while condition can be replaced with '<negated %s>'",
            "no-while-true-break",
            "Emitted when the condition of a while loop is 'True' unnecessarily.",
        ),
    }

    def visit_while(self, node: nodes.While) -> None:
        if not isinstance(node.test, nodes.Const) or not node.test.bool_value():
            return

        first = node.body[0]
        if isinstance(first, nodes.If) and isinstance(first.body[-1], nodes.Break):
            self.add_message("no-while-true-break", node=node, args=(first.test.as_string()))


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
                    nonglobal_modifiers = [n for n in listener.get_modifiers(node) if n.scope() != node.scope()]
                    if nonglobal_modifiers:
                        self.add_message("no-global-vars", node=node, args=(node.name, nonglobal_modifiers[0].lineno))


class Short(BaseChecker):
    name = "short-problems"
    msgs = {
        "R6601": (
            "Use %s.append(%s) instead of %s.",
            "use-append",
            "Emitted when code extends list by a single argument instead of appending it."
        ),
        "R6602": (
            "Use integral division //.",
            "use-integral-division",
            "Emitted when the code uses float division and converts the result to int."
        ),
        "R6603": (
            "Use isdecimal to test if string contains a number.",
            "use-isdecimal",
            "Emitted when the code uses isdigit or isnumeric."
        ),
        "R6604": (
            "Do not use %s loop with else.",
            "no-loop-else",
            "Emitted when the code contains loop with else block."
        ),
    }

    def _check_extend(self, node: nodes.Call) -> None:
        if isinstance(node.func, nodes.Attribute) and node.func.attrname == "extend" \
                and len(node.args) == 1 \
                and isinstance(node.args[0], nodes.List) and len(node.args[0].elts) == 1:
            self.add_message("use-append", node=node, args=(
                node.func.expr.as_string(),
                node.args[0].elts[0].as_string(),
                node.as_string()
            ))

    def _check_augassign_extend(self, node: nodes.AugAssign) -> None:
        if node.op == "+=" and isinstance(node.value, nodes.List) and len(node.value.elts) == 1:
            self.add_message("use-append", node=node, args=(
                node.target.as_string(),
                node.value.elts[0].as_string(),
                node.as_string())
            )

    def _check_isdecimal(self, node: nodes.Call) -> None:
        if isinstance(node.func, nodes.Attribute) and node.func.attrname in ("isdigit", "isnumeric"):
            self.add_message("use-isdecimal", node=node)

    def _check_div(self, node: nodes.Call) -> None:
        if isinstance(node.func, nodes.Name) and node.func.name == "int" \
                and len(node.args) == 1 \
                and isinstance(node.args[0], nodes.BinOp) and node.args[0].op == "/":
            self.add_message("use-integral-division", node=node)

    def _check_loop_else(self, nodes: List[nodes.NodeNG], parent_name: str) -> None:
        if nodes:
            self.add_message("no-loop-else", node=nodes[0].parent, args=(parent_name))

    def visit_call(self, node: nodes.Call) -> None:
        self._check_extend(node)
        self._check_isdecimal(node)
        self._check_div(node)

    def visit_augassign(self, node: nodes.AugAssign) -> None:
        self._check_augassign_extend(node)

    def visit_while(self, node: nodes.While) -> None:
        self._check_loop_else(node.orelse, "while")

    def visit_for(self, node: nodes.For) -> None:
        self._check_loop_else(node.orelse, "for")


def register(linter: "PyLinter") -> None:
    """This required method auto registers the checker during initialization.
    :param linter: The linter to register the checker to.
    """
    linter.register_checker(AugmentAssignments(linter))
    linter.register_checker(ImproveForLoop(linter))
    linter.register_checker(SimplifiableIf(linter))
    linter.register_checker(NoWhileTrue(linter))
    linter.register_checker(NoGlobalVars(linter))
    linter.register_checker(Short(linter))
