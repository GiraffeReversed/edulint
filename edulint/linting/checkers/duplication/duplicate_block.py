from typing import List

from astroid import nodes  # type: ignore

from edulint.linting.analyses.antiunify import cprint  # noqa: F401
from edulint.linting.analyses.reaching_definitions import (
    get_vars_defined_before,
    get_vars_used_after,
    get_control_statements,
)
from edulint.linting.checkers.utils import get_statements_count, get_token_count
from edulint.linting.checkers.duplication.utils import (
    Fixed,
    type_mismatch,
    saves_enough_tokens,
    to_node,
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
    extra_args = get_vars_defined_before(core)
    return_vals_needed = len(get_vars_used_after(core))
    control_needed = len(get_control_statements(core))

    # generate calls in ifs
    calls = []
    for i in range(len(to_aunify)):
        params = [s[i] for s in seen]
        call = nodes.Call()
        call.func = nodes.Name("AUX")
        call.args = [to_node(param) for param in params] + [
            nodes.Name(varname) for varname, _scope in extra_args.keys()
        ]
        if return_vals_needed + control_needed == 0:
            calls.append(call)
        else:
            assign = nodes.Assign()
            assign.targets = [
                nodes.AssignName(f"<r{i}>") for i in range(control_needed + return_vals_needed)
            ]
            assign.value = call
            calls.append(assign)

            # generate management for returned control flow
            for i in range(control_needed):
                test = nodes.BinOp("is")
                test.postinit(left=nodes.Name(f"<r{i}>"), right=nodes.Const(None))
                if_ = nodes.If()
                if_.test = test
                if_.body = [nodes.Return()]  # placeholder for a control
                calls.append(if_)

    # generate function
    fun_def = nodes.FunctionDef(name="AUX")
    fun_def.args = nodes.Arguments()
    fun_def.args.postinit(
        args=[nodes.AssignName(avar.name) for avar in seen.values()]
        + [nodes.AssignName(varname) for varname, _scope in extra_args.keys()],
        defaults=None,
        kwonlyargs=[],
        kw_defaults=None,
        annotations=[],
    )
    fun_def.body = core if isinstance(core, list) else [core]

    return Fixed(
        "similar-to-function",
        get_token_count(calls) + get_token_count(fun_def),
        get_statements_count(calls, include_defs=False, include_name_main=True)
        + get_statements_count(fun_def, include_defs=False, include_name_main=True),
        (
            len(to_aunify),
            get_statements_count(core, include_defs=False, include_name_main=True),
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
    if not saves_enough_tokens(tokens_before, stmts_before, fixed):
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


def returns_used_value(return_, returned_values, node):
    # TODO do properly, not by checking for substring
    if node == return_ or any(r in node.as_string() for r in returned_values):
        return True

    for parent in node.node_ancestors():
        if parent == return_:
            return True
        if any(r in parent.as_string() for r in returned_values):
            return True

    return False


def similar_to_call(self, to_aunify: List[List[nodes.NodeNG]], core, avars) -> bool:
    possible_callees = get_possible_callees(to_aunify)
    if len(possible_callees) != 1:
        return False

    i, function = possible_callees[0]
    args = function.args.arguments
    argnames = {arg.name for arg in args}

    for avar in avars:
        sub = avar.subs[i]
        if not isinstance(sub, nodes.Name) or sub.name not in argnames:
            return False

    vars_used_after = get_vars_used_after(core)
    if len(vars_used_after) != 0:
        if len(function.body) <= len(to_aunify[i]):
            return False
        last = function.body[len(to_aunify[i])]  # handle unreachable code
        if not isinstance(last, nodes.Return) or last.value is None:
            return False

        returned_values = (
            [last.value.as_string()]
            if not isinstance(last.value, nodes.Tuple)
            else [e.as_string() for e in last.value.elts]
        )
        for users in vars_used_after.values():
            for node in users:
                if not returns_used_value(last, returned_values, node):
                    return False

    other_body = to_aunify[0] if i != 0 else to_aunify[1]
    first = other_body[0]
    last = other_body[-1]
    self.add_message(
        "similar-to-call",
        line=first.fromlineno,
        col_offset=first.col_offset,
        end_lineno=last.tolineno,
        end_col_offset=last.col_offset,
        args=(function.name),
    )
    return True
