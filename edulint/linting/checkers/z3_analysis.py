from typing import List, Optional, Dict, Tuple

from astroid import nodes
from edulint.linting.checkers.utils import get_const_value, is_integer, is_number, is_float
from edulint.linting.analyses.types import guess_type, Type

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
)


EXCLUDED_COMPARES_IN_Z3 = {"in", "not in", "is", "is not"}
EXCLUDED_OPERATIONS_IN_Z3 = {"<<", ">>", "|", "&", "^", "@"}


def _is_bool_node(node: Optional[nodes.NodeNG]) -> bool:
    return (
        node is None
        or isinstance(node, nodes.BoolOp)
        or (isinstance(node, nodes.UnaryOp) and node.op == "not")
    )


def _is_variable_in_pure_expression(node: nodes.NodeNG) -> bool:
    # In pure expressions, the value of a function call should not change, nor should the value of any other types listed below.
    return isinstance(node, (nodes.Name, nodes.Subscript, nodes.Attribute, nodes.Call))


def _is_expression_with_nonlinear_arithmetic(node: nodes.NodeNG) -> bool:
    return (
        isinstance(node, nodes.BinOp)
        and not is_number(node)
        and (
            node.op == "**"
            or (node.op == "/" and not is_number(node.right))
            or ((node.op == "//" or node.op == "%") and not is_integer(node.right))
        )
    )


def _not_allowed_node(
    node: nodes.NodeNG, is_descendant_of_integer_operation: bool, parent: Optional[nodes.NodeNG]
) -> bool:
    return (
        (
            isinstance(node, nodes.BinOp)
            and (
                node.op is None
                or node.left is None
                or node.right is None
                or node.op in EXCLUDED_OPERATIONS_IN_Z3
                or ((node.op == "%" or node.op == "//") and is_float(node.right))
                or (node.op == "/" and (is_descendant_of_integer_operation))
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
            and (
                node.value is None
                or isinstance(node.value, bool)
                and not _is_bool_node(parent)
                or not isinstance(node.value, (int, float))
                or (is_descendant_of_integer_operation and isinstance(node.value, float))
            )
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
    Returns False if the condition has some not allowed operations in Z3.
    For operations that are nonlinear arithmetic this function just makes them a variable (for example m % n
    would be a variable)
    """
    if _not_allowed_node(node, is_descendant_of_integer_operation, parent):
        return False

    if _is_abs_function(node):
        return initialize_variables(
            node.args[0], initialized_variables, is_descendant_of_integer_operation, node
        )

    nonlinear_arithmetic = _is_expression_with_nonlinear_arithmetic(node)

    # Thanks to the purity of the original node we can work with all these types as variables.
    if _is_variable_in_pure_expression(node) or nonlinear_arithmetic:
        variable_key = node.as_string()
        variable = initialized_variables.get(variable_key)

        if isinstance(node, nodes.Call) and (
            variable_key.startswith("str") or variable_key.startswith("chr")
        ):
            return False

        added_new_var = False

        if variable is None:
            added_new_var = True
            initialized_variables[variable_key] = (
                Int(str(len(initialized_variables)))
                if is_descendant_of_integer_operation
                else Real(str(len(initialized_variables)))
            )
        elif is_descendant_of_integer_operation and variable.is_real():
            added_new_var = True
            initialized_variables[variable_key] = Int(variable.decl().name())

        if added_new_var and not isinstance(node, nodes.Call) and not nonlinear_arithmetic:
            guessed_type = guess_type(node)
            if guessed_type is None:
                return True  # Here should be False, but it makes the results much worse.

            if is_descendant_of_integer_operation:
                return guessed_type.has_only(Type.INT)

            return guessed_type.has_only([Type.BOOL, Type.FLOAT, Type.INT])

        return True

    if isinstance(node, nodes.BinOp) and (node.op == "%" or node.op == "//"):
        return initialize_variables(node.left, initialized_variables, True, node)

    if isinstance(node, (nodes.BoolOp, nodes.Compare, nodes.UnaryOp, nodes.BinOp)):
        for child in node.get_children():
            if not initialize_variables(
                child, initialized_variables, is_descendant_of_integer_operation, node
            ):
                return False

    return True


def _convert_to_bool_if_necessary(
    node: nodes.NodeNG, parent: nodes.NodeNG, z3_node_representation: Optional[ExprRef]
) -> Tuple[Optional[ExprRef], bool]:
    "returns a tuple with possibly converted expression as the first value and the second indicates whether the conversion happend or not"
    if z3_node_representation is None:
        return None, False

    # Because in python when a number 'x' is converted to bool it is equivalent to converting it to 'x != 0'
    if _is_bool_node(parent) and not (
        _is_bool_node(node)
        or isinstance(node, nodes.Compare)
        or (isinstance(node, nodes.Const) and isinstance(node.value, bool))
    ):
        return z3_node_representation != 0, True

    return z3_node_representation, False


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
) -> tuple[Optional[ExprRef], bool]:
    """
    We assume that the expression is pure in the sense of _is_pure_expression from simplifiable_if.
    Before using this function you have to use the initialize_variables funcion on all nodes that
    you are interested about, to fill in the initialized_variables dictionary with variables of
    correct types.

    Returns a tuple, where the first value is the converted condition (or None) and the second value
    indicates whether conversion from possibly not boolean value to boolean happened (for example
    instead of 'x' it would return 'x != 0' and True, indicating that there was a conversion).
    """
    if node is None:
        return None, False

    conversion_to_bool = False

    if _is_abs_function(node):
        expr, conversion_to_bool = convert_condition_to_z3_expression(
            node.args[0], initialized_variables, node
        )
        expr, bool_conversion = _convert_to_bool_if_necessary(node, parent, Abs(expr))
        return expr, bool_conversion or conversion_to_bool

    if _is_variable_in_pure_expression(node) or _is_expression_with_nonlinear_arithmetic(node):
        return _convert_to_bool_if_necessary(node, parent, initialized_variables[node.as_string()])

    if isinstance(node, nodes.BoolOp):
        operands = []
        for operand in node.values:
            converted_condition, bool_conversion = convert_condition_to_z3_expression(
                operand, initialized_variables, node
            )
            conversion_to_bool = conversion_to_bool or bool_conversion

            expr, bool_conversion = _convert_to_bool_if_necessary(node, parent, converted_condition)
            conversion_to_bool = conversion_to_bool or bool_conversion

            if expr is None:
                return None, False

            operands.append(expr)

        return (And(operands) if node.op == "and" else Or(operands)), conversion_to_bool

    if isinstance(node, nodes.Compare):
        left, bool_conversion = convert_condition_to_z3_expression(
            node.left, initialized_variables, node
        )
        conversion_to_bool = bool_conversion or conversion_to_bool

        right, bool_conversion = convert_condition_to_z3_expression(
            node.ops[0][1], initialized_variables, node
        )
        conversion_to_bool = bool_conversion or conversion_to_bool

        comparison = node.ops[0][0]

        if left is None or right is None:
            return None, False

        if comparison == "==":
            converted_condition = left == right
        elif comparison == "!=":
            converted_condition = left != right
        elif comparison == "<":
            converted_condition = left < right
        elif comparison == "<=":
            converted_condition = left <= right
        elif comparison == ">":
            converted_condition = left > right
        elif comparison == ">=":
            converted_condition = left >= right
        else:
            return None, False

        return converted_condition, conversion_to_bool

    if isinstance(node, nodes.BinOp):
        left, conversion_to_bool = convert_condition_to_z3_expression(
            node.left, initialized_variables, node
        )
        right = None

        if node.op in ("+", "-", "*"):
            right, bool_conversion = convert_condition_to_z3_expression(
                node.right, initialized_variables, node
            )
            conversion_to_bool = conversion_to_bool or bool_conversion

        if (
            left is None
            or (node.op in ("+", "-", "*") and right is None)
            or ((node.op == "%" or node.op == "//") and not is_int(left))
        ):
            return None, False

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

        converted_condition, bool_conversion = _convert_to_bool_if_necessary(node, parent, z3_expr)
        return converted_condition, (bool_conversion or conversion_to_bool)

    if isinstance(node, nodes.Const):
        return _convert_to_bool_if_necessary(node, parent, _convert_const_to_z3(node))

    if isinstance(node, nodes.UnaryOp):
        expr, conversion_to_bool = convert_condition_to_z3_expression(
            node.operand, initialized_variables, node
        )

        if expr is None:
            return None, False

        if node.op == "-":
            expr = -expr
        elif node.op == "not":
            expr = Not(expr)

        converted_condition, bool_conversion = _convert_to_bool_if_necessary(node, parent, expr)
        return converted_condition, (bool_conversion or conversion_to_bool)

    # Should not be reachable
    return None, False


Z3_TACTIC = Then(
    Tactic("simplify"),
    Tactic("solve-eqs"),
    Tactic("propagate-values"),
    Tactic("solve-eqs"),
    Tactic("smt"),
)


def unsatisfiable(condition: ExprRef, rlimit=1700) -> bool:
    solver = Z3_TACTIC.solver()
    solver.set("rlimit", rlimit)
    solver.add(condition)
    return solver.check() == unsat


def implies(condition1: ExprRef, condition2: ExprRef, rlimit=1700) -> bool:
    """
    Returns if implication 'condition1 => condition2' is valid. (but if it cannot decide return False)

    Warning: Can give incorrect answer if variable used in expressions involving % or // can
    be of type float. (for example: x % 2 != 0 => x % 2 == 1, when x is int it is true,
    but not when x is float)
    """
    return unsatisfiable(And(condition1, Not(condition2)), rlimit)


def first_implied_index(
    condition: ExprRef, conditions: List[ExprRef], rlimit=1700
) -> Optional[int]:
    for i in range(len(conditions)):
        if implies(condition, conditions[i], rlimit):
            return i

    return None


def all_implied_indeces(condition: ExprRef, conditions: List[ExprRef], rlimit=1700) -> List[int]:
    implied_indeces = []

    for i in range(len(conditions)):
        if implies(condition, conditions[i], rlimit):
            implied_indeces.append(i)

    return implied_indeces
