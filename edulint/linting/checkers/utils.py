from typing import (
    Any,
    TypeVar,
    Generic,
    List,
    Iterable,
    Union,
    Optional,
    Tuple,
    cast,
    Callable,
    Dict,
    Generator,
)
from functools import reduce
from astroid import nodes, Uninferable  # type: ignore
import sys
import inspect
import operator
from pylint.checkers import utils  # type: ignore
from z3 import (
    ExprRef,
    ArithRef,
    Int,
    Real,
    And,
    Or,
    IntVal,
    RealVal,
    BoolVal,
    is_int,
    Then,
    Tactic,
    Not,
    unsat,
    Abs,
    Solver,
)

EXPRESSION_TYPES = (
    nodes.Subscript,
    nodes.Attribute,
    nodes.BinOp,
    nodes.BoolOp,
    nodes.Call,
    nodes.Compare,
    nodes.Const,
    nodes.List,
    nodes.Dict,
    nodes.Set,
    nodes.GeneratorExp,
    nodes.IfExp,
    nodes.Lambda,
    nodes.Tuple,
    nodes.UnaryOp,
)


def eprint(*args: Any, **kwargs: Any) -> None:
    print(*args, file=sys.stderr, **kwargs)


T = TypeVar("T")


class BaseVisitor(Generic[T]):
    default: T = None  # type: ignore

    def combine(self, results: List[T]) -> T:
        if not results:
            return self.default  # type: ignore
        return results[-1]

    def visit(self, node: nodes.NodeNG) -> T:
        return node.accept(self)  # type: ignore

    def visit_many(self, nodes: Iterable[nodes.NodeNG]) -> T:
        return self.combine([self.visit(node) for node in nodes])


def generic_visit(self: BaseVisitor[T], node: nodes.NodeNG) -> T:
    return self.combine([self.visit(child) for child in node.get_children()])


for name, obj in inspect.getmembers(nodes, inspect.isclass):
    setattr(BaseVisitor, f"visit_{obj.__name__.lower()}", generic_visit)


# rightfully stolen from
# https://github.com/PyCQA/pylint/blob/ca80f03a43bc39e4cc2c67dc99817b3c9f13b8a6/pylint/checkers/refactoring/recommendation_checker.py
def is_builtin(node: nodes.NodeNG, function: Optional[str] = None) -> bool:
    inferred = utils.safe_infer(node)
    if not inferred:
        return False
    return utils.is_builtin_object(inferred) and function is None or inferred.name == function


PURE_FUNCTIONS = {
    "abs",
    "max",
    "min",
    "round",
    "sqrt",
    "len",
    "sum",
    "sorted",
    "reversed",
    "int",
    "float",
    "str",
    "ord",
    "chr",
}

EXPR_FUNCTIONS = PURE_FUNCTIONS | {"all", "any", "map", "filter"}


def is_pure_builtin(node: nodes.NodeNG) -> bool:
    inferred = utils.safe_infer(node)
    return is_builtin(node) and inferred and inferred.name in PURE_FUNCTIONS


def is_number(node: nodes.NodeNG) -> bool:
    const_val = get_const_value(node)
    return isinstance(const_val, (int, float)) and not isinstance(const_val, bool)


def is_integer(node: nodes.NodeNG) -> bool:
    const_val = get_const_value(node)
    return isinstance(const_val, int) and not isinstance(const_val, bool)


EXCLUDED_COMPARES_IN_Z3 = {"in", "not in", "is", "is not"}
EXCLUDED_OPERATIONS_IN_Z3 = {"<<", ">>", "|", "&", "^", "@", "**"}


def _is_bool_node(node: Optional[nodes.NodeNG]) -> bool:
    return (
        node is None
        or isinstance(node, nodes.BoolOp)
        or (isinstance(node, nodes.UnaryOp) and node.op == "not")
    )


def _not_allowed_node(
    node: nodes.NodeNG, is_descendant_of_integer_operation: bool, parent: Optional[nodes.NodeNG]
) -> bool:
    return (
        (
            isinstance(node, nodes.BinOp)
            and (
                node.op is None
                or node.op in EXCLUDED_OPERATIONS_IN_Z3
                or (node.op == "%" and not is_integer(node.right))
                or (
                    node.op == "/"
                    and (is_descendant_of_integer_operation or not is_number(node.right))
                )
                or (node.op == "//" and not is_integer(node.right))
            )
        )
        or (
            isinstance(node, nodes.Compare)
            and (
                len(node.ops) != 1
                or node.ops[0][0] in EXCLUDED_COMPARES_IN_Z3
                or not _is_bool_node(parent)
            )
        )
        or (
            isinstance(node, nodes.UnaryOp)
            and (node.op == "~" or (node.op == "not" and not _is_bool_node(parent)))
        )
        or (isinstance(node, nodes.BoolOp) and (node.op is None or not _is_bool_node(parent)))
        or (
            isinstance(node, (nodes.Const))
            and (node.value is None or isinstance(node.value, bool) and not _is_bool_node(parent))
        )
    )


def _is_abs_function(node: nodes.NodeNG) -> bool:
    return (
        isinstance(node, nodes.Call)
        and isinstance(node.func, nodes.Name)
        and node.func.name == "abs"
    )


def initialize_variables(
    node: nodes.NodeNG,
    initialized_variables: Dict[str, ArithRef],
    is_descendant_of_integer_operation: bool,
    parent: Optional[nodes.NodeNG],
) -> bool:
    """
    Supposes that node is pure. And we exclude bit operations, because Z3 supports them only on bitvectors.
    Returns False if the condition has some not allowed operations in Z3 or operations that are too difficult
    for Z3 and would take a lot of time (like the '**' operator)
    """
    if _not_allowed_node(node, is_descendant_of_integer_operation, parent):
        return False

    if isinstance(node, nodes.BinOp) and (node.op == "%" or node.op == "//"):
        return initialize_variables(node.left, initialized_variables, True, node)

    if isinstance(node, (nodes.BoolOp, nodes.Compare, nodes.UnaryOp, nodes.BinOp)):
        for child in node.get_children():
            if not initialize_variables(
                child, initialized_variables, is_descendant_of_integer_operation, node
            ):
                return False

        return True

    if _is_abs_function(node):
        return initialize_variables(
            node.args[0], initialized_variables, is_descendant_of_integer_operation, node
        )

    # Thanks to the purity of the original node we can work with all these types as variables.
    if isinstance(node, (nodes.Name, nodes.Subscript, nodes.Attribute, nodes.Call)):
        variable_key = node.as_string()
        variable = initialized_variables.get(variable_key)

        if variable is None:
            initialized_variables[variable_key] = (
                Int(str(len(initialized_variables)))
                if is_descendant_of_integer_operation
                else Real(str(len(initialized_variables)))
            )
        elif is_descendant_of_integer_operation and variable.is_real():
            initialized_variables[variable_key] = Int(variable.decl().name())

    return True


def _is_variable_in_pure_expression(node: nodes.NodeNG) -> bool:
    # In pure expressions, the value of a function call should not change, nor should the value of any other types listed below.
    return isinstance(node, (nodes.Name, nodes.Subscript, nodes.Attribute, nodes.Call))


def _convert_to_bool_if_necessary(
    node: nodes.NodeNG, parent: nodes.NodeNG, z3_node_representation: Optional[ExprRef]
) -> Optional[ExprRef]:
    if z3_node_representation is None:
        return None

    # Because in python when a number 'x' is converted to bool it is equivalent to converting it to 'x != 0'
    if _is_bool_node(parent) and not (
        _is_bool_node(node)
        or isinstance(node, nodes.Compare)
        or (isinstance(node, nodes.Const) and isinstance(node.value, bool))
    ):
        return z3_node_representation != 0

    return z3_node_representation


def _convert_const_to_z3(node: nodes.Const) -> Optional[ExprRef]:
    if isinstance(node.value, bool):
        return BoolVal(node.value)

    if isinstance(node.value, int):
        return IntVal(node.value)

    if isinstance(node.value, float):
        return RealVal(node.value)

    return None


def convert_condition_to_z3_expression(
    node: Optional[nodes.NodeNG],
    initialized_variables: Dict[str, ArithRef],
    parent: Optional[nodes.NodeNG],
) -> Optional[ExprRef]:
    """
    We assume that the expression is pure in the sense of _is_pure_expression from simplifiable_if.
    Before using this function you have to use the initialize_variables funcion on all nodes that
    you are interested about, to fill in the initialized_variables dictionary with variables of
    correct types.
    """
    if node is None:
        return None

    if _is_abs_function(node):
        expr = convert_condition_to_z3_expression(node.args[0], initialized_variables, node)
        return _convert_to_bool_if_necessary(node, parent, Abs(expr))

    if _is_variable_in_pure_expression(node):
        return _convert_to_bool_if_necessary(node, parent, initialized_variables[node.as_string()])

    if isinstance(node, nodes.BoolOp):
        operands = []
        for operand in node.values:
            expr = _convert_to_bool_if_necessary(
                node,
                parent,
                convert_condition_to_z3_expression(operand, initialized_variables, node),
            )
            if expr is None:
                return None

            operands.append(expr)

        return And(operands) if node.op == "and" else Or(operands)

    if isinstance(node, nodes.Compare):
        left = convert_condition_to_z3_expression(node.left, initialized_variables, node)
        right = convert_condition_to_z3_expression(node.ops[0][1], initialized_variables, node)
        comparison = node.ops[0][0]

        if left is None or right is None:
            return None

        if comparison == "==":
            return left == right

        if comparison == "!=":
            return left != right

        if comparison == "<":
            return left < right

        if comparison == "<=":
            return left <= right

        if comparison == ">":
            return left > right

        if comparison == ">=":
            return left >= right

        return None

    if isinstance(node, nodes.BinOp):
        left = convert_condition_to_z3_expression(node.left, initialized_variables, node)
        right = None

        if node.op in ("+", "-", "*"):
            right = convert_condition_to_z3_expression(node.right, initialized_variables, node)

        if (
            left is None
            or (node.op in ("+", "-", "*") and right is None)
            or ((node.op == "%" or node.op == "//") and not is_int(left))
        ):
            return None

        z3_expr: Optional[ExprRef] = None

        if node.op == "%":
            modulo = get_const_value(node.right)
            z3_expr = left % get_const_value(node.right) if modulo > 1 else None
        elif node.op == "//":
            z3_expr = left / get_const_value(node.right)
        elif node.op == "/":
            z3_expr = left / float(get_const_value(node.right))
        elif node.op == "+":
            z3_expr = left + right
        elif node.op == "-":
            z3_expr = left - right
        elif node.op == "*":
            z3_expr = left * right

        return _convert_to_bool_if_necessary(node, parent, z3_expr)

    if isinstance(node, nodes.Const):
        return _convert_to_bool_if_necessary(node, parent, _convert_const_to_z3(node))

    if isinstance(node, nodes.UnaryOp):
        expr = convert_condition_to_z3_expression(node.operand, initialized_variables, node)

        if expr is None:
            return None

        if node.op == "-":
            expr = -expr
        elif node.op == "not":
            expr = Not(expr)

        return _convert_to_bool_if_necessary(node, parent, expr)

    # Should not be reachable
    return None


Z3_TACTIC = Then(
    Tactic("simplify"),
    Tactic("solve-eqs"),
    Tactic("propagate-values"),
    Tactic("solve-eqs"),
    Tactic("smt"),
)


def implies(condition1: ExprRef, condition2: ExprRef, rlimit=1700) -> bool:
    """
    Returns if implication 'condition1 => condition2' is valid.

    Warning: Can give incorrect answer if variable used in expressions involving % or // can
    be of type float. (for example: x % 2 != 0 => x % 2 == 1, when x is int it is true,
    but not when x is float)
    """
    solver = Z3_TACTIC.solver()
    solver.set("rlimit", rlimit)
    solver.add(And(condition1, Not(condition2)))
    return solver.check() == unsat


def first_implied_index(
    condition: ExprRef, conditions: List[ExprRef], rlimit=1700
) -> Optional[int]:
    for i in range(len(conditions)):
        if implies(condition, conditions[i]):
            return i

    return None


def all_implied_indeces(condition: ExprRef, conditions: List[ExprRef], rlimit=1700) -> List[int]:
    implied_indeces = []

    for i in range(len(conditions)):
        if implies(condition, conditions[i]):
            implied_indeces.append(i)

    return implied_indeces


def is_multi_assign(node: nodes.NodeNG) -> bool:
    return hasattr(node, "targets")


def is_assign(node: nodes.NodeNG) -> bool:
    return hasattr(node, "target")


def is_any_assign(node: nodes.NodeNG) -> bool:
    return is_assign(node) or is_multi_assign(node)


def get_assigned_to(node: nodes.NodeNG) -> List[nodes.NodeNG]:
    if is_multi_assign(node):
        return cast(List[nodes.NodeNG], node.targets)
    if is_assign(node):
        return [node.target]
    return []


Named = Union[nodes.Name, nodes.Attribute, nodes.AssignName]


def is_named(node: nodes.NodeNG) -> bool:
    return hasattr(node, "name") or hasattr(node, "attrname")


def get_name(node: Named) -> str:
    return node.as_string()


def get_range_params(
    node: nodes.NodeNG,
) -> Optional[Tuple[nodes.NodeNG, nodes.NodeNG, nodes.NodeNG]]:
    if (
        not isinstance(node, nodes.Call)
        or node.func.as_string() != "range"
        or len(node.args) < 1
        or len(node.args) > 3
    ):
        return None

    default_start = nodes.Const(0)
    default_step = nodes.Const(1)

    if len(node.args) == 1:
        return default_start, node.args[0], default_step

    if len(node.args) == 2:
        return node.args[0], node.args[1], default_step

    if len(node.args) == 3:
        return node.args[0], node.args[1], node.args[2]

    assert False, "unreachable"


# based on https://docs.python.org/3/library/operator.html
UNARY_SYMBOL_TO_OP = {
    "+": operator.pos,
    "-": operator.neg,
    "not": operator.not_,
    "~": operator.invert,
}

BINARY_SYMBOL_TO_OP = {
    "+": operator.add,
    "/": operator.truediv,
    "//": operator.floordiv,
    "&": operator.and_,
    "^": operator.xor,
    "|": operator.or_,
    "**": operator.pow,
    "is": operator.is_,
    "is not": operator.is_not,
    "<<": operator.lshift,
    "%": operator.mod,
    "*": operator.mul,
    ">>": operator.rshift,
    "-": operator.sub,
    "<": operator.lt,
    "<=": operator.le,
    "==": operator.eq,
    "!=": operator.ne,
    ">=": operator.ge,
    ">": operator.gt,
    "and": lambda lt, rt: lt and rt,
    "or": lambda lt, rt: lt or rt,
}


def get_const_value_rec(node: Any) -> Any:
    if not isinstance(node, nodes.NodeNG):
        return node

    if isinstance(node, nodes.Const):
        return node.value

    if isinstance(node, nodes.UnaryOp):
        return UNARY_SYMBOL_TO_OP[node.op](get_const_value_rec(node.operand))

    if isinstance(node, nodes.BinOp):
        return BINARY_SYMBOL_TO_OP[node.op](
            get_const_value_rec(node.left), get_const_value_rec(node.right)
        )

    if isinstance(node, nodes.BoolOp):
        assert len(node.values) > 1
        return reduce(BINARY_SYMBOL_TO_OP[node.op], map(get_const_value_rec, node.values))

    raise ValueError(f"{type(node)} cannot be evaluated")


def get_const_value(node: Any) -> Any:
    try:
        return get_const_value_rec(node)
    except ValueError:
        return None


def infer_to_value(node: nodes.NodeNG) -> Optional[nodes.NodeNG]:
    if isinstance(node, nodes.Name):
        inferred = utils.safe_infer(node)
        return None if inferred is Uninferable else inferred

    if isinstance(
        node,
        (
            nodes.Const,
            nodes.List,
            nodes.Set,
            nodes.Dict,
            nodes.ListComp,
            nodes.DictComp,
            nodes.Call,
        ),
    ):
        return node

    return None


def is_parents_elif(node: nodes.If) -> bool:
    parent = node.parent
    return isinstance(parent, nodes.If) and parent.has_elif_block() and parent.orelse[0] == node


def has_else_block(node: Union[nodes.For, nodes.While, nodes.If, nodes.IfExp]):
    if isinstance(node, nodes.IfExp):
        return True
    return len(node.orelse) > 0 and (not isinstance(node, nodes.If) or not node.has_elif_block())


def get_lines_between(first: nodes.NodeNG, last: nodes.NodeNG, including_last: bool) -> int:
    assert first.fromlineno <= last.fromlineno

    if including_last:
        return last.tolineno - first.fromlineno + 1
    return last.fromlineno - first.fromlineno


def is_main_block(statement: nodes.If) -> bool:
    """
    Return whether or not <statement> is the main block.
    """
    return (
        isinstance(statement, nodes.If)
        and isinstance(statement.test, nodes.Compare)
        and isinstance(statement.test.left, nodes.Name)
        and isinstance(statement.test.left, nodes.Name)
        and statement.test.left.name == "__name__"
        and len(statement.test.ops) == 1
        and statement.test.ops[0][0] == "=="
        and isinstance(statement.test.ops[0][1], nodes.Const)
        and statement.test.ops[0][1].value == "__main__"
    )


def is_block_comment(stmt: nodes.NodeNG) -> bool:
    return (
        isinstance(stmt, nodes.Expr)
        and isinstance(stmt.value, nodes.Const)
        and isinstance(stmt.value.value, str)
    )


def get_statements_count(
    node: Union[nodes.NodeNG, List[nodes.NodeNG]], include_defs: bool, include_name_main: bool
) -> int:
    def count(nodes: List[nodes.NodeNG]) -> int:
        return sum(get_statements_count(node, include_defs, include_name_main) for node in nodes)

    if isinstance(node, list):
        return count(node)

    if isinstance(node, (nodes.ClassDef, nodes.FunctionDef)):
        return 1 + count(node.body) if include_defs else 0

    if isinstance(node, (nodes.Import, nodes.ImportFrom)):
        return 1 if include_defs else 0

    if isinstance(node, (nodes.For, nodes.While, nodes.If)):
        if is_main_block(node) and not include_name_main:
            return 0
        return 1 + count(node.body) + (1 if has_else_block(node) else 0) + count(node.orelse)

    if isinstance(node, nodes.Module):
        return count(node.body)

    if isinstance(node, nodes.TryExcept):
        return 2 + count(node.body) + sum(count(h.body) for h in node.handlers) + count(node.orelse)

    if isinstance(node, nodes.TryFinally):
        return 2 + count(node.body) + count(node.finalbody)

    if isinstance(node, nodes.With):
        return 1 + count(node.body)

    return 1


class TokenCountingVisitor(BaseVisitor[int]):
    default = 0

    @classmethod
    def combine(cls, results: List[int]) -> int:
        return sum(results) + 1

    def _visit_with_else(self, node: Union[nodes.If, nodes.For, nodes.While]) -> int:
        return self.visit_many(node.get_children()) + (1 if has_else_block(node) else 0)

    def visit_if(self, node: nodes.If) -> int:
        return self._visit_with_else(node)

    def visit_for(self, node: nodes.For) -> int:
        return self._visit_with_else(node)

    def visit_while(self, node: nodes.While) -> int:
        return self._visit_with_else(node)

    def visit_ifexp(self, node: nodes.IfExp) -> int:
        return self._visit_with_else(node)

    def visit_expr(self, node: nodes.Expr) -> int:
        return self.visit(node.value)


def get_token_count(node: Union[nodes.NodeNG, List[nodes.NodeNG]]) -> int:
    visitor = TokenCountingVisitor()
    if isinstance(node, (list, tuple)):
        return visitor.visit_many(node) - 1
    else:
        return visitor.visit(node)


NEGATED_OP = {
    ">=": "<",
    "<=": ">",
    ">": "<=",
    "<": ">=",
    "==": "!=",
    "!=": "==",
    "is": "is not",
    "is not": "is",
    "in": "not in",
    "not in": "in",
    "and": "or",
    "or": "and",
}


def is_negation(lt: nodes.NodeNG, rt: nodes.NodeNG, negated_rt: bool) -> bool:
    def ops_match(lt: nodes.NodeNG, rt: nodes.NodeNG, lt_transform: Callable[[str], str]) -> bool:
        return all(lt_transform(lt_op) == rt_op for (lt_op, _), (rt_op, _) in zip(lt.ops, rt.ops))

    def to_values(node: nodes.NodeNG) -> List[nodes.NodeNG]:
        return [node.left] + [val for _, val in node.ops]

    def all_are_negations(
        lt_values: List[nodes.NodeNG], rt_values: List[nodes.NodeNG], new_rt_negated: bool
    ) -> bool:
        return all(is_negation(ll, rr, new_rt_negated) for ll, rr in zip(lt_values, rt_values))

    def strip_nots(node: nodes.NodeNG, negated_rt: bool) -> Tuple[nodes.NodeNG, bool]:
        while isinstance(node, nodes.UnaryOp) and node.op == "not":
            negated_rt = not negated_rt
            node = node.operand
        return node, negated_rt

    def is_mod_two(node: nodes.NodeNG):
        return isinstance(node, nodes.BinOp) and node.op == "%" and get_const_value(node.right) == 2

    # TODO allow x % 2 > 0
    def is_eq_mod_two(node: nodes.NodeNG):
        if len(node.ops) != 1:
            return False

        left, (op, right) = node.left, node.ops[0]
        if op not in ("==", "!=") or is_mod_two(left) == is_mod_two(right):
            return False

        # MAYBE check if value equal to mod is 0 or 1?
        return True

    def mod_two_negation(lt: nodes.NodeNG, rt: nodes.NodeNG):
        if not is_eq_mod_two(lt) or not is_eq_mod_two(rt):
            return False

        lt_lt, (_, lt_rt) = lt.left, lt.ops[0]
        rt_lt, (_, rt_rt) = rt.left, rt.ops[0]

        lt_mod, lt_val = (lt_lt, lt_rt) if is_mod_two(lt_lt) else (lt_rt, lt_lt)
        rt_mod, rt_val = (rt_lt, rt_rt) if is_mod_two(rt_lt) else (rt_rt, rt_lt)

        return are_identical(lt_mod.left, rt_mod.left) and not are_identical(lt_val, rt_val)

    lt, negated_rt = strip_nots(lt, negated_rt)
    rt, negated_rt = strip_nots(rt, negated_rt)

    if not isinstance(lt, type(rt)):
        return False

    if isinstance(lt, nodes.BoolOp):
        if len(lt.values) == len(rt.values) and (
            (negated_rt and lt.op == rt.op) or (not negated_rt and NEGATED_OP[lt.op] == rt.op)
        ):
            return all_are_negations(lt.values, rt.values, negated_rt)
        return False

    if isinstance(lt, nodes.Compare):
        if len(lt.ops) != len(rt.ops):
            return False

        if negated_rt and ops_match(lt, rt, lambda op: op):
            return all_are_negations(to_values(lt), to_values(rt), negated_rt)

        if not negated_rt and ops_match(lt, rt, lambda op: NEGATED_OP[op]):
            return all_are_negations(to_values(lt), to_values(rt), not negated_rt)

        if not negated_rt and mod_two_negation(lt, rt):
            return True

        return False

    return negated_rt and are_identical(lt, rt)


def are_identical(
    block1: Union[nodes.NodeNG, List[nodes.NodeNG]], block2: Union[nodes.NodeNG, List[nodes.NodeNG]]
) -> bool:
    if isinstance(block1, nodes.NodeNG):
        assert isinstance(block2, nodes.NodeNG)
        block1 = [block1]
        block2 = [block2]

    strings1 = [n.as_string() for n in block1]
    strings2 = [n.as_string() for n in block2]

    return strings1 == strings2
