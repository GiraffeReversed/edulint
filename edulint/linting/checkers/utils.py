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
)
from functools import reduce
from astroid import nodes, Uninferable  # type: ignore
from astroid.const import Context
import sys
import inspect
import operator
from pylint.checkers import utils  # type: ignore
from z3 import ExprRef, ArithRef, Int, Real, And, Or, IntVal, RealVal, BoolVal, is_int

from edulint.linting.analyses.data_dependency import node_to_var

POSTINIT_ARGS = {
    klass: (
        {
            param.name: (
                list
                if param.annotation != inspect.Parameter.empty
                and param.annotation.lower().startswith("list")
                else lambda: None
            )
            for param in inspect.signature(klass.postinit).parameters.values()
            if param.name != "self"
        }
        if klass != nodes.Const and hasattr(klass, "postinit")
        else {}
    )
    for klass in nodes.ALL_NODE_CLASSES
}


def requires_data_dependency_analysis(func):
    def inner(self, node: nodes.NodeNG, *args, **kwargs):
        if not node.root().cfg_loc.var_events.successful:
            return
        func(self, node, *args, **kwargs)

    return inner


def new_node(node_type, **attr_vals):
    attr_vals_before = {
        attr: val for attr, val in attr_vals.items() if attr not in POSTINIT_ARGS[node_type].keys()
    }
    attr_vals_after = {
        attr: attr_vals.get(attr, default()) for attr, default in POSTINIT_ARGS[node_type].items()
    }

    if node_type == nodes.Arguments:
        attr_vals_before["kwarg"] = attr_vals_before.get("kwarg", "")
        attr_vals_before["vararg"] = attr_vals_before.get("vararg", "")
        node = node_type(parent=None, **attr_vals_before)
    elif node_type == nodes.Module:
        node = node_type(**attr_vals_before)
    else:
        if node_type == nodes.ImportFrom:
            attr_vals_before["fromname"] = attr_vals_before.pop("modname")
        node = node_type(
            lineno=0, col_offset=0, end_lineno=0, end_col_offset=0, parent=None, **attr_vals_before
        )

    if not isinstance(node, nodes.Const) and hasattr(node, "postinit"):
        node.postinit(**attr_vals_after)

    return node


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


# solution using inference at
# https://github.com/PyCQA/pylint/blob/ca80f03a43bc39e4cc2c67dc99817b3c9f13b8a6/pylint/checkers/refactoring/recommendation_checker.py
def is_builtin(node: nodes.NodeNG, function: Optional[str] = None) -> bool:
    assert function is None or utils.is_builtin(function)
    node_var = node_to_var(node)
    return node_var is None and (
        function is None or (isinstance(node, nodes.Name) and node.name == function)
    )


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


def is_pure_node(node: nodes.NodeNG):
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


def is_pure_expression(node: nodes.NodeNG) -> bool:
    if not is_pure_node(node):
        return False

    children = node.get_children()
    if isinstance(node, nodes.Call):
        # the first child of Call is always the function itself and we know it is pure by now.
        next(children)

    for child in children:
        if not is_pure_expression(child):
            return False

    return True


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
    )


def _initialize_variables(
    node: nodes.NodeNG,
    initialized_variables: Dict[str, ArithRef],
    is_descendant_of_integer_operation: bool,
    parent: Optional[nodes.NodeNG],
) -> bool:
    # Supposes that node is pure. And we exclude bit operations, because Z3 supports them only on bitvectors.
    # Returns False if the condition has some not allowed operations in Z3 or operations that are too difficult
    # for Z3 and would take a lot of time (like the '**' operator)
    if _not_allowed_node(node, is_descendant_of_integer_operation, parent):
        return False

    if isinstance(node, nodes.BinOp) and (node.op == "%" or node.op == "//"):
        return _initialize_variables(node.left, initialized_variables, True, node)

    if isinstance(node, (nodes.BoolOp, nodes.Compare, nodes.UnaryOp, nodes.BinOp)):
        for child in node.get_children():
            if not _initialize_variables(
                child, initialized_variables, is_descendant_of_integer_operation, node
            ):
                return False

        return True

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
    # We assume that the expression is pure in the sense of _is_pure_expression from simplifiable_if

    # TODO - erase this: I have no chance of knowing when the variable should be bool or when it should be a number (Real or Int)

    if node is None:
        return None

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
        right = convert_condition_to_z3_expression(node.ops[0][1])
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
        if node.op in ("+", "-", "*"):
            right = convert_condition_to_z3_expression(node.right, initialized_variables, node)

        if (
            left is None
            or right is None
            or ((node.op == "%" or node.op == "//") and not is_int(left))
        ):
            return None

        z3_expr: Optional[ExprRef] = None

        if node.op == "%":
            z3_expr = left % get_const_value(node.right)
        elif node.op == "//":
            z3_expr = left // get_const_value(node.right)
        elif node.op == "/":
            z3_expr = left / get_const_value(node.right)
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
        return _convert_to_bool_if_necessary(node, parent, expr)

    # Should not be reachable
    return None


def implies(node1: nodes.NodeNG, node2: nodes.NodeNG) -> bool:
    # TODO
    return False


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

    default_start = new_node(nodes.Const, value=0)
    default_step = new_node(nodes.Const, value=1)

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
    except (ValueError, KeyError):
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

    if isinstance(node, (nodes.Try, nodes.TryStar)):
        return (
            2
            + count(node.body)
            + sum(count(h.body) for h in node.handlers)
            + count(node.orelse)
            + count(node.finalbody)
        )

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

        return have_same_value(lt_mod.left, rt_mod.left) and not have_same_value(lt_val, rt_val)

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

    return negated_rt and have_same_value(lt, rt)


def have_same_value(lt: nodes.NodeNG, rt: nodes.NodeNG):
    # TODO improve, for example not all functions are pure
    return are_identical(lt, rt)


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
