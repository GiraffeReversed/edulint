from typing import List

from astroid import nodes  # type: ignore

from edulint.linting.analyses.antiunify import antiunify, cprint, core_as_string  # noqa: F401
from edulint.linting.analyses.cfg.utils import syntactic_children_locs, get_cfg_loc
from edulint.linting.analyses.var_events import VarEventType
from edulint.linting.analyses.data_dependency import (
    get_vars_defined_before,
    get_vars_defined_before_core,
    get_vars_used_after_core,
    get_control_statements,
    get_events_for,
    node_to_var,
    GENERATING_EVENTS,
)
from edulint.linting.checkers.utils import (
    get_statements_count,
    get_token_count,
    EXPRESSION_TYPES,
    new_node,
    are_identical,
)
from edulint.linting.checkers.duplication.utils import (
    Fixed,
    length_mismatch,
    type_mismatch,
    called_aunify_var,
    saves_enough_tokens,
    to_node,
    to_start_lines,
)

### similar to function


def get_fixed_by_function(to_aunify, core, avars):
    # compute necessary arguments from different values
    seen = {}
    for avar in avars:
        var_vals = tuple(avar.subs)
        old_avar = seen.get(var_vals, avar)

        if old_avar != avar:
            continue
        seen[var_vals] = avar

    # compute extras
    extra_args = {
        v for vars_uses in get_vars_defined_before_core(core).values() for v in vars_uses.keys()
    }
    return_vals_needed = sum(
        len(vars_uses) for vars_uses in get_vars_used_after_core(core).values()
    )
    control_needed = len(get_control_statements(core))

    # generate calls in ifs
    calls = []
    for i in range(len(to_aunify)):
        params = [s[i] for s in seen]
        call = new_node(
            nodes.Call,
            func=new_node(nodes.Name, name="AUX"),
            args=[to_node(param) for param in params]
            + [new_node(nodes.Name, name=var.name) for var in extra_args],
        )
        if return_vals_needed + control_needed == 0:
            calls.append(call)
        else:
            assign = new_node(
                nodes.Assign,
                targets=[
                    new_node(nodes.AssignName, name=f"<r{i}>")
                    for i in range(control_needed + return_vals_needed)
                ],
                value=call,
            )
            calls.append(assign)

            # generate management for returned control flow
            for i in range(control_needed):
                test = new_node(
                    nodes.BinOp,
                    op="is",
                    left=new_node(nodes.Name, name=f"<r{i}>"),
                    right=new_node(nodes.Const, value=None),
                )
                if_ = new_node(
                    nodes.If, test=test, body=[new_node(nodes.Return)]
                )  # placeholder for a control
                calls.append(if_)

    # generate function
    fun_def = new_node(
        nodes.FunctionDef,
        name="AUX",
        args=new_node(
            nodes.Arguments,
            args=[new_node(nodes.AssignName, name=avar.name) for avar in seen.values()]
            + [new_node(nodes.AssignName, name=var.name) for var in extra_args],
        ),
        body=core if isinstance(core, list) else [core],
    )

    return Fixed(
        "similar-block-to-function",
        get_token_count(calls) + get_token_count(fun_def),
        get_statements_count(calls, include_defs=False, include_name_main=True)
        + get_statements_count(fun_def, include_defs=False, include_name_main=True),
        (
            len(to_aunify),
            get_statements_count(core, include_defs=False, include_name_main=True),
            to_start_lines(to_aunify),
        ),
    )


def similar_to_function(self, to_aunify: List[List[nodes.NodeNG]], core, avars) -> bool:
    if type_mismatch(avars):
        return False

    tokens_before = sum(get_token_count(node) for node in to_aunify)
    stmts_before = sum(
        get_statements_count(node, include_defs=False, include_name_main=True) for node in to_aunify
    )

    fixed = get_fixed_by_function(to_aunify, core, avars)
    if not saves_enough_tokens(tokens_before, stmts_before, fixed.tokens, fixed.statements):
        return False

    message_id, _tokens, _statements, message_args = fixed

    first = to_aunify[0][0]
    last = to_aunify[0][-1]
    self.add_message(
        message_id,
        line=first.fromlineno,
        col_offset=first.col_offset,
        end_lineno=last.tolineno,
        end_col_offset=last.col_offset,
        args=message_args,
    )
    return True


### similar to call


def is_possible_callee(function: nodes.FunctionDef, sub_aunify):
    assert len(sub_aunify) <= len(function.body)
    if len(sub_aunify) == len(function.body):
        return True

    return sub_aunify == function.body[: len(sub_aunify)] and isinstance(
        function.body[len(sub_aunify)], nodes.Return
    )


def get_possible_callees(to_aunify):
    possible_callees = []

    for i, sub_aunify in enumerate(to_aunify):
        if not isinstance(sub_aunify[0].parent, nodes.FunctionDef):
            continue
        function = sub_aunify[0].parent
        if is_possible_callee(function, sub_aunify):
            possible_callees.append((i, function))

    return possible_callees


def returns_used_value(returned_values, i, j, avars, use):
    assert isinstance(use, (nodes.Name, nodes.AssignName))

    original_name = use.name
    for avar in avars:
        if avar.subs[j] == use.name:
            use.name = avar.subs[i]
            break

    current = use
    while not current.is_statement:
        if any(are_identical(current, val) for val in returned_values):
            use.name = original_name
            return True
        current = current.parent

    use.name = original_name
    return False


def returns_used_values(returned_values, i, j, avars, uses):
    return all(returns_used_value(returned_values, i, j, avars, use) for use in uses)


def var_only_modified(var, vars_defined_before, nodes):
    return (
        var in vars_defined_before
        and len(list(get_events_for([var], nodes, (VarEventType.ASSIGN, VarEventType.REASSIGN))))
        == 0
    )


def similar_to_call(self, to_aunify: List[List[nodes.NodeNG]], core, avars) -> bool:
    possible_callees = get_possible_callees(to_aunify)
    if len(possible_callees) != 1:
        return False

    i, function = possible_callees[0]

    result = antiunify(
        to_aunify,
        stop_on=lambda avars: length_mismatch(avars)
        or type_mismatch(avars, allowed_mismatches=[{nodes.Name, t} for t in EXPRESSION_TYPES]),
        stop_on_after_renamed_identical=lambda avars: called_aunify_var(avars),
        require_name_consistency=True,
    )
    if result is None:
        return False
    core, avars = result

    if not all(
        (isinstance(avar.subs[i], str) and isinstance(avar.parent, (nodes.Name, nodes.AssignName)))
        or isinstance(avar.subs[i], (nodes.Name, nodes.AssignName))
        for avar in avars
    ):
        return False

    syntactic_children = {
        j: [loc.node for loc in syntactic_children_locs([c.subs[j] for c in core])]
        for j in range(len(to_aunify))
    }
    if any(
        node in syntactic_children[j]
        for avar in avars
        if not isinstance(avar.parent, (nodes.Name, nodes.AssignName))
        for j, sub in enumerate(avar.subs)
        if i != j
        for _var, defs in get_vars_defined_before([sub]).items()
        for node in defs
    ):
        return False

    return_ = function.body[len(to_aunify[i])] if len(function.body) > len(to_aunify[i]) else None
    if return_ is not None and not isinstance(return_, nodes.Return):
        return False

    if return_ is None or return_.value is None:
        returned_values = []
    elif not isinstance(return_.value, nodes.Tuple):
        returned_values = [return_.value]
    else:
        returned_values = return_.value.elts

    vars_defined_before = get_vars_defined_before_core(core)

    # no avar outside scope
    for avar in avars:
        if isinstance(avar.parent, (nodes.Name, nodes.AssignName)):
            avar = avar.parent

        callee_node = avar.subs[i]
        assert isinstance(callee_node, (nodes.Name, nodes.AssignName))
        callee_var = node_to_var(callee_node)
        if callee_var is None or any(
            get_cfg_loc(def_.node).node not in syntactic_children[i]
            and (
                not isinstance(def_.node.parent, nodes.Arguments)
                or def_.node.parent.parent != function
            )
            for event in get_events_for([callee_var], [callee_node], GENERATING_EVENTS)
            for def_ in event.definitions
        ):
            return False

    vars_used_after = get_vars_used_after_core(core)
    if i in vars_used_after:
        vars_used_after.pop(i)

    for j, vars_uses in vars_used_after.items():
        sub_vars_defined_before = vars_defined_before[j]
        for var, uses in vars_uses.items():
            if not var_only_modified(
                var, sub_vars_defined_before, core
            ) and not returns_used_values(returned_values, i, j, avars, uses):
                return False

    if (
        # function called only for a side effect
        all(
            var_only_modified(var, vars_defined_before[j], [c.subs[j] for c in core])
            for j, vars_uses in vars_used_after.items()
            for var in vars_uses.keys()
        )
        # no value used later is actually returned
        and not any(
            returns_used_values(returned_values, i, j, avars, uses)
            for j, vars_uses in vars_used_after.items()
            for uses in vars_uses.values()
        )
        and not saves_enough_tokens(
            sum(get_token_count(ns) for ns in to_aunify),
            sum(
                get_statements_count(ns, include_defs=False, include_name_main=False)
                for ns in to_aunify
            ),
            get_token_count(to_aunify[i])
            # 3 = function name + call + assign
            + (len(to_aunify) - 1) * (3 + len(function.args.arguments) + len(returned_values)),
            get_statements_count(to_aunify[i], include_defs=False, include_name_main=False)
            + len(to_aunify)
            - 1,
        )
    ):
        return False

    other_body = to_aunify[0] if i != 0 else to_aunify[1]
    first = other_body[0]
    last = other_body[-1]
    self.add_message(
        "similar-block-to-call",
        line=first.fromlineno,
        col_offset=first.col_offset,
        end_lineno=last.tolineno,
        end_col_offset=last.col_offset,
        args=(function.name),
    )
    return True


### control function


def similar_to_block(checker, to_aunify: List[List[nodes.NodeNG]]) -> bool:
    result = antiunify(
        to_aunify,
        stop_on=lambda avars: length_mismatch(avars)
        or type_mismatch(avars, allowed_mismatches=[{nodes.Name, t} for t in EXPRESSION_TYPES]),
        stop_on_after_renamed_identical=lambda avars: called_aunify_var(avars),
    )
    if result is None:
        return False
    core, avars = result

    if all(isinstance(vals[0], nodes.FunctionDef) for vals in to_aunify):
        return False  # TODO hint use common helper function

    if similar_to_call(checker, to_aunify, core, avars):
        return True
    return similar_to_function(checker, to_aunify, core, avars)
