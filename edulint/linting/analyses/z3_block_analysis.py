from __future__ import annotations

from typing import List, Tuple, Dict, Set, Optional, Union, TYPE_CHECKING
from astroid import nodes

if TYPE_CHECKING:
    import z3  # pyright: ignore[reportMissingImports]
else:
    from edulint.linting.analyses._z3 import z3

from edulint.linting.checkers.utils import (
    is_pure_expression,
    is_chained_assignment,
    has_more_assign_targets,
    get_assign_targets,
)

from edulint.linting.analyses.data_dependency import vars_in, modified_in
from edulint.linting.analyses.utils import may_contain_mutable_var

from edulint.linting.analyses.z3_analysis import (
    implies,
    initialize_variables,
    convert_condition_to_z3_expression,
    create_prefixed_var,
    convert_to_bool,
    _is_expression_with_nonlinear_arithmetic,
)


ALLOWED_EXPR_NODES_FOR_Z3_BLOCK_ANALYSIS = (
    nodes.BinOp,
    nodes.BoolOp,
    nodes.Call,
    nodes.Compare,
    nodes.Const,
    nodes.Name,
    nodes.Tuple,
    nodes.UnaryOp,
)

END_NODES = (
    nodes.Break,
    nodes.Continue,
    nodes.Raise,
    nodes.Return,
)

ALWAYS_PURE_ALLOWED_NODES_FOR_Z3_BLOCK_ANALYSIS = (
    *END_NODES,
    nodes.Pass,
)

ALLOWED_NODES_FOR_Z3_BLOCK_ANALYSIS = (
    *ALLOWED_EXPR_NODES_FOR_Z3_BLOCK_ANALYSIS,
    *ALWAYS_PURE_ALLOWED_NODES_FOR_Z3_BLOCK_ANALYSIS,
    nodes.Assign,
    nodes.AnnAssign,
    nodes.AugAssign,
    nodes.Expr,
    nodes.Assert,
    nodes.IfExp,
    nodes.If,
)


def is_assignment(node: nodes.NodeNG) -> bool:
    return isinstance(node, (nodes.Assign, nodes.AnnAssign, nodes.AugAssign))


def check_purity_for_Z3_block_analysis(node: nodes.NodeNG) -> bool:
    if isinstance(node, nodes.Assert):
        return is_pure_expression(node.test)

    if isinstance(node, ALLOWED_EXPR_NODES_FOR_Z3_BLOCK_ANALYSIS):
        return is_pure_expression(node)

    if isinstance(node, ALWAYS_PURE_ALLOWED_NODES_FOR_Z3_BLOCK_ANALYSIS):
        return True

    if isinstance(node, (nodes.Assign, nodes.AnnAssign, nodes.AugAssign, nodes.Expr)):
        return check_purity_for_Z3_block_analysis(node.value)

    # not doing nested IfExps
    if isinstance(node, nodes.IfExp):
        return (
            is_pure_expression(node.test)
            and is_pure_expression(node.body)
            and is_pure_expression(node.orelse)
        )

    return False


def _vars_from_non_linear_arithmetic_are_modified_in(
    node: nodes.NodeNG, nodes: List[nodes.NodeNG]
) -> bool:
    """
    Note that could be enhanced by checking only the variables from expressions of this node
    that are non-linear arithmetic (given by function _is_expression_with_nonlinear_arithmetic()
    from z3_analysis) or that are a function call (not including abs()).

    Here we check whether any variable from this node is modified in `nodes` for simplification,
    most likely it will be only the two variables anyway, like in expressions `m % n == 0`, ...
    """
    return modified_in(list(vars_in(node).keys()), nodes)


def _allowed_node_for_Z3_block_analysis(node: nodes.NodeNG) -> bool:
    return (
        isinstance(node, ALLOWED_NODES_FOR_Z3_BLOCK_ANALYSIS)
        and not is_chained_assignment(node)
        and (not isinstance(node, nodes.IfExp) or is_assignment(node.parent))
    )


def _initialize_variables_in_node(
    node: nodes.NodeNG,
    context: List[nodes.NodeNG],
    initialized_variables: Dict[str, z3.ArithRef],
) -> bool:
    if isinstance(node, nodes.Assert):
        node = node.test

    nodes_tmp = [node]

    if isinstance(node, nodes.AugAssign) and (
        (assigned := _get_assigned_expression_in_AugAssign(node)) is None
        or _is_expression_with_nonlinear_arithmetic(assigned)
    ):
        return False

    if isinstance(node, nodes.Assign) and has_more_assign_targets(node):
        nodes_tmp = list(node.value.get_children())
    elif is_assignment(node):
        nodes_tmp = [node.value]

    nodes_for_initialization: List[nodes.NodeNG] = []
    for node in nodes_tmp:
        if isinstance(node, nodes.IfExp):
            nodes_for_initialization.extend([node.test, node.body, node.orelse])
        else:
            nodes_for_initialization.append(node)

    for current_node in nodes_for_initialization:
        if not isinstance(current_node, ALLOWED_EXPR_NODES_FOR_Z3_BLOCK_ANALYSIS):
            return False
        # because the variables from `m%n == 0` for example are modified later we cannot take `m%n` as
        # a variable, because it would have different value later then now.
        dont_make_up_new_vars = _vars_from_non_linear_arithmetic_are_modified_in(
            current_node, context
        )
        if not initialize_variables(
            current_node, initialized_variables, False, None, dont_make_up_new_vars
        ):
            return False

    return True


def validate_and_initialize_variables_for_Z3_block_analysis(
    node: nodes.NodeNG,
    initialized_variables: Dict[str, z3.ArithRef],
    context: List[nodes.NodeNG],
) -> bool:
    """
    This function must be used on the `node` (if statement, while loop, ...) on which you want to perform 'z3 block analysis'.

    Args:
        `initialized_variables`: just create variable with empty dictionary and then pass it into this function
        `context`: all the nodes that you will be working in the z3 block analysis (should be consecutive), for
                   example if working with some consecutive ifs, you will put the nodes.If nodes that represent them into the context.

    Returns:
        `True` if successful and `False` if not.
    """
    if may_contain_mutable_var(node):
        return False

    nodes_to_validate = [node]

    while nodes_to_validate:
        current_node = nodes_to_validate.pop()

        if isinstance(current_node, nodes.If):
            nodes_to_validate.extend(current_node.get_children())
            continue

        if not (
            _allowed_node_for_Z3_block_analysis(current_node)
            and check_purity_for_Z3_block_analysis(current_node)
        ) or (isinstance(current_node, END_NODES) and current_node.parent is node):
            return False

        if isinstance(current_node, ALWAYS_PURE_ALLOWED_NODES_FOR_Z3_BLOCK_ANALYSIS) or isinstance(
            current_node, nodes.Expr
        ):
            continue

        if not _initialize_variables_in_node(current_node, context, initialized_variables):
            return False

    return True


def _change_assertions_and_vars_after_elif_block(
    if_conditions: List[z3.ExprRef],
    return_encountered: bool,
    new_assertions: List[z3.ExprRef],
    var_changes: Dict[str, z3.ArithRef],
    assertions: List[z3.ExprRef],
    current_condition: z3.ExprRef,
    changed_vars_in_any_branch: Set[str],
    var_changes_in_each_branch: List[Dict[str, z3.ArithRef]],
):
    previous_conditions_negated = [z3.Not(cond) for cond in if_conditions]

    if return_encountered:
        assertions.append(
            z3.Implies(z3.And(previous_conditions_negated), z3.Not(current_condition))
            if len(if_conditions) > 0
            else z3.Not(current_condition)
        )
    else:
        for assertion in new_assertions:
            assertions.append(
                z3.Implies(
                    (
                        z3.And(*previous_conditions_negated, current_condition)
                        if len(if_conditions) > 0
                        else current_condition
                    ),
                    assertion,
                )
            )

        for var_name in var_changes.keys():
            changed_vars_in_any_branch.add(var_name)

        var_changes_in_each_branch.append((var_changes, return_encountered))

        if_conditions.append(current_condition)


def _how_var_changed_after_if(
    var_name: str,
    if_conditions: List[z3.ExprRef],
    var_changes_in_each_branch: List[Tuple[Dict[str, z3.ArithRef], bool]],
    var_value_before_if: z3.ArithRef,
    current_block: int,
    has_else_block: bool,
) -> z3.ExprRef:
    if current_block >= len(var_changes_in_each_branch) and not has_else_block:
        return var_value_before_if

    var_changes, return_found = var_changes_in_each_branch[current_block]

    if current_block == len(var_changes_in_each_branch) - 1 and has_else_block:
        return var_changes.get(var_name, var_value_before_if)

    if return_found:
        return _how_var_changed_after_if(
            var_name,
            if_conditions,
            var_changes_in_each_branch,
            var_value_before_if,
            current_block + 1,
            has_else_block,
        )

    return z3.If(
        if_conditions[current_block],
        var_changes.get(var_name, var_value_before_if),
        _how_var_changed_after_if(
            var_name,
            if_conditions,
            var_changes_in_each_branch,
            var_value_before_if,
            current_block + 1,
            has_else_block,
        ),
    )


def _update_relations_between_vars(
    var_name: str,
    var_value: z3.ExprRef,
    var_rewrite_counts: Dict[str, int],
    accumulated_relations_between_vars: List[z3.ExprRef],
    initialized_variables: Dict[str, z3.ArithRef],
) -> z3.ArithRef:
    var_rewrite_counts[var_name] += 1
    prefix = str(var_rewrite_counts[var_name])

    var = create_prefixed_var(prefix, initialized_variables[var_name], var_name)

    accumulated_relations_between_vars.append(
        (convert_to_bool(var) if z3.is_bool(var_value) else var) == var_value
    )

    return var


def _create_new_var_after_if(
    var_name: str,
    if_conditions: List[z3.ExprRef],
    var_changes_in_each_branch: List[Tuple[Dict[str, z3.ArithRef], bool]],
    accumulated_relations_between_vars: List[z3.ExprRef],
    var_rewrite_counts: Dict[str, int],
    initialized_variables: Dict[str, z3.ArithRef],
    has_else_block: bool,
) -> z3.ArithRef:
    new_var_value = _how_var_changed_after_if(
        var_name,
        if_conditions,
        var_changes_in_each_branch,
        initialized_variables[var_name],
        0,
        has_else_block,
    )

    return _update_relations_between_vars(
        var_name,
        new_var_value,
        var_rewrite_counts,
        accumulated_relations_between_vars,
        initialized_variables,
    )


def _changed_vars_after_if(
    node: nodes.If,
    initialized_variables: Dict[str, z3.ArithRef],
    accumulated_relations_between_vars: List[z3.ExprRef],
    var_rewrite_counts: Dict[str, int],
) -> Optional[Tuple[Dict[str, z3.ArithRef], List[z3.ExprRef], bool]]:
    new_vars: Dict[str, z3.ArithRef] = {}
    assertions: List[z3.ExprRef] = []
    changed_vars_in_any_branch: Set[str] = set()

    always_returns = True
    if_conditions: List[z3.ExprRef] = []
    var_changes_in_each_branch: List[Tuple[Dict[str, z3.ArithRef], bool]] = []
    current_node = node
    while True:
        current_condition = convert_condition_to_z3_expression(
            current_node.test, initialized_variables, None
        )[0]
        after_block = _changed_vars_after_block(
            current_node.body,
            initialized_variables.copy(),
            accumulated_relations_between_vars,
            var_rewrite_counts,
        )

        if current_condition is None or after_block is None:
            return None

        var_changes, new_assertions, return_encountered = after_block
        always_returns = always_returns and return_encountered

        _change_assertions_and_vars_after_elif_block(
            if_conditions,
            return_encountered,
            new_assertions,
            var_changes,
            assertions,
            current_condition,
            changed_vars_in_any_branch,
            var_changes_in_each_branch,
        )

        if not current_node.has_elif_block():
            break

        current_node = current_node.orelse[0]

    has_else_block = False
    if len(current_node.orelse) > 0:
        after_block = _changed_vars_after_block(
            current_node.orelse,
            initialized_variables.copy(),
            accumulated_relations_between_vars,
            var_rewrite_counts,
        )

        if after_block is None:
            return None

        var_changes, new_assertions, return_encountered = after_block
        always_returns = always_returns and return_encountered

        if return_encountered:
            # this is negation of z3.And([z3.Not(cond) for cond in if_conditions]) (ie condition that holds when we get to else)
            assertions.append(z3.Or(if_conditions))
        else:
            for assertion in new_assertions:
                assertions.append(
                    z3.Implies(z3.And([z3.Not(cond) for cond in if_conditions]), assertion)
                )

            for var_name in var_changes.keys():
                changed_vars_in_any_branch.add(var_name)

            var_changes_in_each_branch.append((var_changes, return_encountered))

        has_else_block = True
    else:
        always_returns = False

    if always_returns:
        return {}, [], True

    i = len(var_changes_in_each_branch) - 1
    while i >= 0 and var_changes_in_each_branch[i][1]:
        var_changes_in_each_branch.pop()
        i -= 1

    for var_name in changed_vars_in_any_branch:
        new_vars[var_name] = _create_new_var_after_if(
            var_name,
            if_conditions,
            var_changes_in_each_branch,
            accumulated_relations_between_vars,
            var_rewrite_counts,
            initialized_variables,
            has_else_block,
        )

    return new_vars, assertions, False


def _convert_expression_in_assignment_to_Z3(
    node: nodes.NodeNG, initialized_variables: Dict[str, z3.ArithRef]
) -> Optional[z3.ExprRef]:
    if isinstance(node, nodes.IfExp):
        test = convert_condition_to_z3_expression(node.test, initialized_variables, None)[0]
        body = convert_condition_to_z3_expression(node.body, initialized_variables, node.parent)[0]
        orelse = convert_condition_to_z3_expression(
            node.orelse, initialized_variables, node.parent
        )[0]

        if test is None or body is None or orelse is None:
            return None

        return z3.If(test, body, orelse)

    return convert_condition_to_z3_expression(node, initialized_variables, node.parent)[0]


def _get_assigned_expression_in_AugAssign(node: nodes.AugAssign) -> Optional[nodes.NodeNG]:
    assigned_expression = nodes.BinOp(
        op=node.op[:-1],
        lineno=node.lineno,
        col_offset=node.col_offset,
        parent=node,
        end_lineno=node.end_lineno,
        end_col_offset=node.end_col_offset,
    )

    if not isinstance(node.target, nodes.AssignName):
        return None

    assigned_expression.postinit(
        nodes.Name(
            name=node.target.name,
            lineno=node.target.lineno,
            col_offset=node.target.col_offset,
            parent=assigned_expression,
            end_lineno=node.target.end_lineno,
            end_col_offset=node.target.end_col_offset,
        ),
        node.value,
    )
    return assigned_expression


def _update_vars_after_assignment(
    assignment: Union[nodes.Assign, nodes.AnnAssign, nodes.AugAssign],
    initialized_variables: Dict[str, z3.ArithRef],
    accumulated_relations_between_vars: List[z3.ExprRef],
    var_rewrite_counts: Dict[str, int],
) -> Optional[Dict[str, z3.ArithRef]]:
    if isinstance(assignment, nodes.Assign) and has_more_assign_targets(assignment):
        values = list(assignment.value.get_children())
    elif isinstance(assignment, nodes.AugAssign):
        values = [_get_assigned_expression_in_AugAssign(assignment)]
    else:
        values = [assignment.value]

    targets = get_assign_targets(assignment)

    new_vars: Dict[str, z3.ArithRef] = {}

    for i, target in enumerate(targets):
        if not isinstance(target, nodes.AssignName):
            return None

        if target.name not in initialized_variables:
            continue

        converted = _convert_expression_in_assignment_to_Z3(values[i], initialized_variables)

        if converted is None:
            return None

        var = _update_relations_between_vars(
            target.name,
            converted,
            var_rewrite_counts,
            accumulated_relations_between_vars,
            initialized_variables,
        )

        new_vars[target.name] = var

    initialized_variables.update(new_vars)
    return new_vars


def _changed_vars_after_block(
    block: List[nodes.NodeNG],
    initialized_variables: Dict[str, z3.ArithRef],
    accumulated_relations_between_vars: List[z3.ExprRef],
    var_rewrite_counts: Dict[str, int],
) -> Optional[Tuple[Dict[str, z3.ArithRef], List[z3.ExprRef], bool]]:
    new_vars: Dict[str, z3.ArithRef] = {}
    assertions: List[z3.ExprRef] = []

    for node in block:
        if is_assignment(node):
            updated_vars = _update_vars_after_assignment(
                node,
                initialized_variables,
                accumulated_relations_between_vars,
                var_rewrite_counts,
            )

            if updated_vars is None:
                return None

            new_vars.update(updated_vars)
        elif isinstance(node, END_NODES):
            return ({}, [], True)
        elif isinstance(node, nodes.If):
            after_if = _changed_vars_after_if(
                node,
                initialized_variables,
                accumulated_relations_between_vars,
                var_rewrite_counts,
            )

            if after_if is None:
                return None

            var_changes, new_assertions, always_returns = after_if

            if always_returns:
                return ({}, [], True)

            new_vars.update(var_changes)
            initialized_variables.update(var_changes)
            assertions.extend(new_assertions)
        elif isinstance(node, nodes.Assert):
            converted = convert_condition_to_z3_expression(node.test, initialized_variables, None)[
                0
            ]
            if converted is None:
                return None

            assertions.append(converted)

    return new_vars, assertions, False


def convert_conditions_with_blocks_after_each_to_Z3(
    conditions: List[List[nodes.NodeNG]],
    blocks: List[List[nodes.NodeNG]],
    initialized_variables: Dict[str, z3.ArithRef],
) -> Tuple[z3.BoolRef, List[List[z3.ExprRef]]]:
    """
    Before using this function use `validate_and_initialize_variables_for_Z3_block_analysis` to get `initialized_variables`.
    This function converts the `conditions` with `blocks` in between them (there cannot be any cycles).

    Returns:
        A tuple where the first entry is BoolRef representing relations between all the newly created variables and the second entry
        are the `conditions` converted into Z3. (the code blocks between the conditions are taken into account - the first entry)

    When you want to know if when some condition holds and then some block of code is executed whether another condition
    holds you can use this function - `conditions = [[first condition], [second condition]]`, `blocks = [block of code between them]`.
    And then from the result you just test if `relations => (converted_first_cond => converted_second_cond)`.

    Note:
        `conditions[i]` is a list of conditions and `blocks[i]` is a block (list of nodes) between the conditions
        on position `i` and conditions on position `i + 1`. So it must hold that len(conditions) == len(blocks) + 1
    """
    assert len(conditions) == len(blocks) + 1

    accumulated_relations_between_vars: List[z3.ExprRef] = []
    converted_conditions: List[List[z3.ExprRef]] = []

    var_rewrite_counts = {var: 0 for var in initialized_variables}

    for i, conds in enumerate(conditions):
        converted_conditions.append([])
        for cond in conds:
            converted = convert_condition_to_z3_expression(cond, initialized_variables, None)[0]
            if converted is None:
                return (z3.And(), [])

            converted_conditions[i].append(converted)

        if i < len(blocks):
            after_block = _changed_vars_after_block(
                blocks[i],
                initialized_variables.copy(),
                accumulated_relations_between_vars,
                var_rewrite_counts,
            )

            if after_block is None:
                return (z3.And(), [])

            new_vars, assertions, _ = after_block

            initialized_variables.update(new_vars)
            accumulated_relations_between_vars.extend(assertions)

    return z3.And(accumulated_relations_between_vars), converted_conditions


def condition_implies_another_with_block_in_between(
    condition1: nodes.NodeNG,
    block: List[nodes.NodeNG],
    condition2: nodes.NodeNG,
) -> bool:
    """
    Note: Bevare of potential problems when the block contains `asserts`, `returns`, `raise`, `continue`, `break`.
    (should work mostly, but cannot guarantee.)

    Args:
        `condition1`: first condition
        `block`: block in between `condition1` and `condition2` (note that if `condition1` is test condition of `if`,
                 then the `if` node should be part of the block)
        `condition2`: the implied condition

    Returns:
        `True` only when we can be sure that the implication holds.
    """
    initialized_variables: Dict[str, z3.ArithRef] = {}

    for node in (
        [*block, condition2]
        if block and condition1.parent is block[0]
        else [condition1, *block, condition2]
    ):
        if not _allowed_node_for_Z3_block_analysis(
            node
        ) or not validate_and_initialize_variables_for_Z3_block_analysis(
            node, initialized_variables, block
        ):
            return False

    relations_between_vars, conditions = convert_conditions_with_blocks_after_each_to_Z3(
        [[condition1], [condition2]], [block], initialized_variables
    )

    return conditions and implies(
        relations_between_vars, z3.Implies(conditions[0][0], conditions[1][0]), 3000
    )
