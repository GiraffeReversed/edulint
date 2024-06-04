from typing import Optional, Tuple, List, Union

from astroid import nodes  # type: ignore

from edulint.linting.analyses.antiunify import (
    antiunify,
    AunifyVar,
    cprint,  # noqa: F401
    get_sub_variant,
    contains_avar,
)
from edulint.linting.analyses.variable_modification import VarEventType
from edulint.linting.analyses.reaching_definitions import (
    vars_in,
    is_changed_between,
    get_vars_defined_before,
    get_vars_used_after,
    get_control_statements,
)
from edulint.linting.analyses.cfg.utils import get_cfg_loc
from edulint.linting.checkers.utils import (
    is_parents_elif,
    get_lines_between,
    get_statements_count,
    get_token_count,
    has_else_block,
    is_negation,
    are_identical,
)
from edulint.linting.checkers.duplication.utils import (
    Fixed,
    length_mismatch,
    type_mismatch,
    called_aunify_var,
    assignment_to_aunify_var,
    is_duplication_candidate,
    saves_enough_tokens,
    get_loop_repetitions,
    to_node,
)

### constructive helper functions


def extract_from_elif(
    node: nodes.If, result: List[nodes.If] = None
) -> Tuple[bool, List[List[nodes.NodeNG]]]:
    """
    returns True iff elifs end with else
    """

    def count_nested_ifs(ns: List[nodes.NodeNG]) -> int:
        if len(ns) != 1 or not isinstance(ns[0], nodes.If):
            return 0

        if_ = ns[0]
        return max(count_nested_ifs(if_.body), count_nested_ifs(if_.orelse)) + 1

    result = [node] if result is None else result
    if has_else_block(node):
        return True, result

    current = node
    nested_count = count_nested_ifs(node.body)
    while current.has_elif_block():
        elif_ = current.orelse[0]
        result.append(elif_)
        if has_else_block(elif_):
            return True, (
                result
                if nested_count == 0 or nested_count >= len(result)
                else result[:-nested_count]
            )
        current = elif_
    return False, result


def get_bodies(ifs: List[nodes.If]) -> List[List[nodes.NodeNG]]:
    result = []
    for i, if_ in enumerate(ifs):
        result.append(if_.body)
        if i == len(ifs) - 1:
            result.append(if_.orelse)
    return result


def extract_from_siblings(node: nodes.If, seq_ifs: List[nodes.NodeNG]) -> None:
    sibling = node.next_sibling()
    while sibling is not None and isinstance(sibling, nodes.If):
        new: List[nodes.NodeNG] = []
        if not extract_from_elif(sibling, new):
            return
        seq_ifs.append(sibling)
        seq_ifs.extend(new)
        sibling = sibling.next_sibling()


def create_ifs(tests: List[nodes.NodeNG]) -> Tuple[nodes.If, List[nodes.NodeNG]]:
    root = nodes.If()
    if_ = root
    if_bodies = []
    for i, test in enumerate(tests):
        if_.test = test
        if_bodies.append(if_.body)
        if i != len(tests) - 1:
            elif_ = nodes.If()
            if_.orelse = [elif_]
            # elif_.parent = if_
            if_ = elif_
        else:
            if_bodies.append(if_.orelse)
    return root, if_bodies


### testing helper functions


def to_parent(val: AunifyVar) -> nodes.NodeNG:
    parent = val.parent
    if isinstance(parent, (nodes.Const, nodes.Name)):
        parent = parent.parent
    assert parent is not None
    return parent


def is_one_of_parents_ifs(node: nodes.If) -> bool:
    parent = node.parent
    if not isinstance(parent, nodes.If):
        return False

    while isinstance(parent.parent, nodes.If):
        parent = parent.parent

    _ends_with_else, ifs = extract_from_elif(parent)
    if_bodies = get_bodies(ifs)

    return all(any(isinstance(n, nodes.If) for n in body) for body in if_bodies)


def get_common_parent(ns: List[nodes.NodeNG]) -> bool:
    if len(ns) == 0:
        return None

    if len(ns) == 1:
        return to_parent(ns[0])

    fst_parents = [ns[0]] + list(ns[0].node_ancestors())
    other_parents = set.intersection(
        *[{ns[i]} | set(ns[i].node_ancestors()) for i in range(1, len(ns))]
    )

    for parent in fst_parents:
        if parent in other_parents:
            return parent
    return None


def contains_other_duplication(core, avars) -> bool:
    parent = get_common_parent(avars)
    if parent is None:
        body = core
    elif isinstance(parent, (nodes.List, nodes.Tuple, nodes.Dict, nodes.Set)):
        body = list(parent.get_children())
    else:
        return False

    if len(body) < 3:
        return False

    for end, to_aunify in get_loop_repetitions(body):
        if not is_duplication_candidate(to_aunify):
            continue

        result = antiunify(
            to_aunify,
            stop_on=lambda avars: length_mismatch(avars) or type_mismatch(avars),
        )
        if result is not None:
            return True

    return False


def test_variables_change(tests, core, avars):
    vars = vars_in(tests, {VarEventType.READ})
    first_loc = tests[0].cfg_loc
    avars_locs = [get_cfg_loc(to_parent(avar)).node.sub_locs for avar in avars]
    return any(
        is_changed_between(var, first_loc, avar_locs)
        for var in vars.keys()
        for avar_locs in avars_locs
    )


def check_enabled(message_ids: Union[str, List[str]]):
    if isinstance(message_ids, str):
        message_ids = [message_ids]

    def middle(func):
        def inner(self, *args, **kwargs):
            if not any(self.linter.is_message_enabled(mi) for mi in message_ids):
                return None
            result = func(*args, **kwargs)
            if result is None:
                return result

            if len(message_ids) == 1:
                return Fixed(message_ids[0], *result)
            symbol, *result = result
            return Fixed(symbol, *result)

        return inner

    return middle


### identical code before/after branch


def identical_before_after_branch(self, node: nodes.If) -> bool:

    def get_stmts_difference(branches: List[nodes.NodeNG], forward: bool) -> int:
        reference = branches[0]
        compare = branches[1:]
        for i in range(min(map(len, branches))):
            for branch in compare:
                index = i if forward else -i - 1
                if reference[index].as_string() != branch[index].as_string():
                    return i
        return i + 1

    def add_message(
        branches: List[nodes.NodeNG],
        stmts_difference: int,
        defect_node: nodes.NodeNG,
        forward: bool = True,
    ) -> None:
        reference = branches[0]
        first = reference[0 if forward else -stmts_difference]
        last = reference[stmts_difference - 1 if forward else -1]
        lines_difference = get_lines_between(first, last, including_last=True)

        self.add_message(
            "identical-before-after-branch",
            node=defect_node,
            args=(lines_difference, "before" if forward else "after"),
        )

    if not node.orelse or is_parents_elif(node):
        return False

    ends_with_else, ifs = extract_from_elif(node)
    if not ends_with_else:
        return False

    branches = get_bodies(ifs)

    any_message = False
    same_prefix_len = get_stmts_difference(branches, forward=True)
    if same_prefix_len >= 1:
        if all(same_prefix_len == len(b) for b in branches):
            self.add_message("identical-if-branches", node=node)
            return True

        add_message(branches, same_prefix_len, node, forward=True)
        if any(same_prefix_len == len(b) for b in branches):
            return True

        any_message = True

    same_suffix_len = get_stmts_difference(branches, forward=False)
    if same_suffix_len >= 1:
        # allow wip early returns
        if same_suffix_len == 1 and isinstance(branches[0][-1], nodes.Return):
            return any_message
        defect_node = branches[0][-1].parent

        add_message(branches, same_suffix_len, defect_node, forward=False)
        any_message = True
    return any_message


### identical sequential ifs


def identical_seq_ifs(self, node: nodes.If) -> Tuple[bool, Optional[nodes.NodeNG]]:

    def same_ifs_count(seq_ifs: List[nodes.NodeNG], start: int) -> int:
        reference = seq_ifs[start].body
        for i in range(start + 1, len(seq_ifs)):
            # do not suggest join of elif and sibling
            if seq_ifs[start].parent not in seq_ifs[i].node_ancestors():
                return i - start

            compared = seq_ifs[i].body
            if len(reference) != len(compared):
                return i - start
            for j in range(len(reference)):
                if reference[j].as_string() != compared[j].as_string():
                    return i - start
        return len(seq_ifs) - start

    prev_sibling = node.previous_sibling()
    if is_parents_elif(node) or (
        isinstance(prev_sibling, nodes.If) and not extract_from_elif(prev_sibling)[0]
    ):
        return False, None

    ends_with_else, seq_ifs = extract_from_elif(node)
    if ends_with_else:
        return False, None
    extract_from_siblings(node, seq_ifs)

    if len(seq_ifs) == 1:
        return False, None

    i = 0
    last = None
    while i < len(seq_ifs) - 1:
        count = same_ifs_count(seq_ifs, i)
        if count > 1:
            first = seq_ifs[i]
            assert isinstance(seq_ifs[i + count - 1], nodes.If)
            last = seq_ifs[i + count - 1].body[-1]

            self.add_message(
                "identical-seq-ifs",
                line=first.fromlineno,
                col_offset=first.col_offset,
                end_lineno=last.tolineno,
                end_col_offset=last.end_col_offset,
                args=(count,),
            )
        i += count

    if last is None:
        return False, None
    return True, last.parent


### if to restructured


def restructure_twisted_ifs(tests, inner_if: nodes.If, avars):
    if len(tests) > 1 or len(inner_if.orelse) == 0:
        return None

    outer_test = tests[0]
    inner_test = inner_if.test

    pos_pos = get_sub_variant(inner_if.body, 0)
    pos_neg = get_sub_variant(inner_if.orelse, 0)
    neg_pos = get_sub_variant(inner_if.body, 1)
    neg_neg = get_sub_variant(inner_if.orelse, 1)

    # positive and negative branches are twisted
    if not (
        are_identical(pos_pos, neg_neg)
        and are_identical(pos_neg, neg_pos)
        and not contains_avar(inner_test, avars)
    ) and not (
        # branches are correctly structured, but the inner condition is negated
        are_identical(pos_pos, neg_pos)
        and are_identical(pos_neg, neg_neg)
        and is_negation(
            get_sub_variant(inner_test, 0), get_sub_variant(inner_test, 1), negated_rt=False
        )
    ):
        return None

    pp_test = nodes.BoolOp(op="and")
    pp_test.values = [outer_test, inner_test]

    neg_outer_test = nodes.UnaryOp(op="not")
    neg_outer_test.operand = outer_test
    neg_inner_test = nodes.UnaryOp(op="not")
    neg_inner_test.operand = inner_test

    nn_test = nodes.BoolOp(op="and")
    nn_test.values = [neg_outer_test, neg_inner_test]

    test = nodes.BoolOp(op="or")
    test.values = [pp_test, nn_test]

    if_ = nodes.If()
    if_.test = test
    if_.body = inner_if.sub_locs[0].node.body
    if_.orelse = inner_if.sub_locs[0].node.orelse

    return if_


@check_enabled("nested-if-to-restructured")
def get_fixed_by_restructuring_nested(tests, core, avars):
    if len(core) != 1 or not isinstance(core[0], nodes.If):
        return None

    inner_if = core[0]

    if contains_avar(inner_if.test, avars):
        return None

    if_ = nodes.If()
    if_.test = inner_if.test
    to_complete = []

    if not contains_avar(inner_if.body, avars):
        if_.body = inner_if.body
        if_.orelse = to_complete
        to_extract = inner_if.orelse

    elif not contains_avar(inner_if.orelse, avars):
        if_.body = to_complete
        if_.orelse = inner_if.orelse
        to_extract = inner_if.body

    else:
        return None

    new_inner_if, if_bodies = create_ifs(tests)
    to_complete.append(new_inner_if)

    for i in range(len(avars[0].subs)):
        if_bodies[i].extend(get_sub_variant(to_extract, i))

    return (
        get_token_count(if_),
        get_statements_count(if_, include_defs=False, include_name_main=False),
        (),
    )


@check_enabled("twisted-if-to-restructured")
def get_fixed_by_restructuring_twisted(tests, core, avars):
    if len(tests) > 1 or len(core) != 1 or not isinstance(core[0], nodes.If):
        return None

    inner_if = core[0]
    if len(inner_if.orelse) == 0:
        return None

    outer_test = tests[0]
    inner_test = inner_if.test

    pos_pos = get_sub_variant(inner_if.body, 0)
    pos_neg = get_sub_variant(inner_if.orelse, 0)
    neg_pos = get_sub_variant(inner_if.body, 1)
    neg_neg = get_sub_variant(inner_if.orelse, 1)

    # positive and negative branches are twisted
    if not (
        are_identical(pos_pos, neg_neg)
        and are_identical(pos_neg, neg_pos)
        and not contains_avar(inner_test, avars)
    ) and not (
        # branches are correctly structured, but the inner condition is negated
        are_identical(pos_pos, neg_pos)
        and are_identical(pos_neg, neg_neg)
        and is_negation(
            get_sub_variant(inner_test, 0), get_sub_variant(inner_test, 1), negated_rt=False
        )
    ):
        return None

    pp_test = nodes.BoolOp(op="and")
    pp_test.values = [outer_test, inner_test]

    neg_outer_test = nodes.UnaryOp(op="not")
    neg_outer_test.operand = outer_test
    neg_inner_test = nodes.UnaryOp(op="not")
    neg_inner_test.operand = inner_test

    nn_test = nodes.BoolOp(op="and")
    nn_test.values = [neg_outer_test, neg_inner_test]

    test = nodes.BoolOp(op="or")
    test.values = [pp_test, nn_test]

    if_ = nodes.If()
    if_.test = test
    if_.body = inner_if.sub_locs[0].node.body
    if_.orelse = inner_if.sub_locs[0].node.orelse

    return (
        get_token_count(if_),
        get_statements_count(if_, include_defs=False, include_name_main=False),
        (),
    )


### if to ternary

COMPLEX_EXPRESSION_TYPES = (nodes.BinOp,)
# SIMPLE_EXPRESSION_TYPES = (nodes.AugAssign, nodes.Call, nodes.BoolOp, nodes.Compare)


def is_part_of_complex_expression(avars) -> bool:
    for avar in avars:
        has_parent_call = False
        parent = to_parent(avar)
        while parent is not None:
            if isinstance(parent, nodes.Call):
                if has_parent_call:
                    return True
                has_parent_call = True

            # if not isinstance(parent, SIMPLE_EXPRESSION_TYPES):
            if isinstance(parent, COMPLEX_EXPRESSION_TYPES):
                return True

            if hasattr(parent, "cfg_loc"):
                break

            parent = parent.parent

    return False


@check_enabled("if-to-ternary")
def get_fixed_by_ternary(tests, core, avars):
    # the condition would get too complicated
    if len(tests) > 2:
        return None
    # too much place for error
    if len(avars) > 1 and not all(isinstance(avar.parent, nodes.Const) for avar in avars):
        return None
    # do not make complicated expressions even more complicated
    if is_part_of_complex_expression(avars):
        return None

    # generate exprs
    exprs = []
    for avar in avars:
        assert len(avar.subs) == len(tests) + 1
        expr = to_node(avar.subs[-1], avar)
        for test, avar_val in reversed(list(zip(tests, avar.subs))):
            new = nodes.IfExp()
            new.postinit(test=test, body=to_node(avar_val, avar), orelse=expr)
            expr = new

        exprs.append(expr)

    return (
        get_token_count(core) - len(avars) + get_token_count(exprs),  # subtract aunify vars
        get_statements_count(core, include_defs=False, include_name_main=True),
        (),
    )


### if into block

HEADER_ATTRIBUTES = {
    nodes.For: [["target"], ["iter"]],
    nodes.While: [["test"]],
    # nodes.If: ["test"],
    nodes.FunctionDef: [["name"], ["args"]],
    nodes.ExceptHandler: [["name", "type"]],
    nodes.TryExcept: [["body", "handlers"]],
    nodes.TryFinally: [["body", "finalbody"]],
    nodes.With: [["items"]],
}

BODY_ATTRIBUTES = {
    nodes.For: ["body", "orelse"],
    nodes.While: ["body", "orelse"],
    # nodes.If: ["body", "orelse"],
    nodes.FunctionDef: ["body"],
    nodes.ExceptHandler: ["body"],
    nodes.TryExcept: ["body", "handlers", "orelse"],
    nodes.TryFinally: ["body", "finalbody"],
    nodes.With: ["body"],
}


def if_can_be_moved(core, avars):
    if type(core) not in HEADER_ATTRIBUTES.keys():
        return False

    for attr_group in HEADER_ATTRIBUTES[type(core)]:
        if all(contains_avar(getattr(core, attr), avars) for attr in attr_group):
            return False
    return True


def get_fixed_by_moving_if_rec(tests, core, avars):
    if isinstance(core, list):
        if len(core) == 0:
            return []

        avar_indices = []
        for i, stmt in enumerate(core):
            if contains_avar(stmt, avars):
                avar_indices.append(i)

        assert len(avar_indices) > 0
        min_ = avar_indices[0]
        max_ = avar_indices[-1]

        if min_ == max_ and if_can_be_moved(core[min_], avars):
            root = get_fixed_by_moving_if_rec(tests, core[min_], avars)
        else:
            new_body = core[min_ : max_ + 1]
            root, if_bodies = create_ifs(tests)
            for if_body in if_bodies:
                if_body.extend(new_body)

        return core[:min_] + [root] + core[max_ + 1 :]

    assert contains_avar(core, avars) and if_can_be_moved(core, avars)
    new_core = type(core)()

    for attr in [attr for attr_group in HEADER_ATTRIBUTES[type(core)] for attr in attr_group]:
        setattr(new_core, attr, getattr(core, attr))

    for attr in BODY_ATTRIBUTES[type(core)]:
        new_body = get_fixed_by_moving_if_rec(tests, getattr(core, attr), avars)
        setattr(new_core, attr, new_body)

    return new_core


@check_enabled("if-into-block")
def get_fixed_by_moving_if(tests, core, avars):
    # too restrictive -- the change may be before the avar but after the place
    # where the if would be inserted
    if (not isinstance(core, list) and not if_can_be_moved(core, avars)) or (
        isinstance(core, list) and not if_can_be_moved(core[0], avars)
    ):
        return None

    fixed = get_fixed_by_moving_if_rec(tests, core, avars)
    return (
        get_token_count(fixed)
        + sum(
            get_token_count(v) if isinstance(v, nodes.NodeNG) else 0
            for avar in avars
            for v in avar.subs
        ),
        get_statements_count(fixed, include_defs=True, include_name_main=False),
        (),
    )


### if to variables


@check_enabled("if-to-variables")
def get_fixed_by_vars(tests, core, avars):
    root, if_bodies = create_ifs(tests)
    seen = {}
    for avar in avars:
        var_vals = tuple(avar.subs)
        varname = seen.get(var_vals, avar.name)

        if varname != avar.name:
            continue
        seen[var_vals] = avar.name

        for val, body in zip(var_vals, if_bodies):
            assign = nodes.Assign()
            assign.targets = [nodes.AssignName(avar.name)]
            assign.value = to_node(val, avar)
            body.append(assign)

    return (
        get_token_count(root) + get_token_count(core),
        get_statements_count(root, include_defs=False, include_name_main=True)
        + get_statements_count(core, include_defs=False, include_name_main=True),
        (),
    )


### if to function


@check_enabled("similar-to-function-in-if")
def get_fixed_by_function(tests, core, avars):
    root, if_bodies = create_ifs(tests)

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
    vals = [[s[i] for s in seen] for i in range(len(tests) + 1)]
    for if_vals, body in zip(vals, if_bodies):
        call = nodes.Call()
        call.func = nodes.Name("AUX")
        call.args = [to_node(val) for val in if_vals] + [
            nodes.Name(varname) for varname, _scope in extra_args.keys()
        ]
        if return_vals_needed + control_needed == 0:
            body.append(call)
        else:
            assign = nodes.Assign()
            assign.targets = [
                nodes.AssignName(f"<r{i}>") for i in range(control_needed + return_vals_needed)
            ]
            assign.value = call
            body.append(assign)

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

    # generate management for returned values
    if control_needed > 0:
        root = [root]
        for i in range(control_needed):
            test = nodes.BinOp("is")
            test.postinit(left=nodes.Name(f"<r{i}>"), right=nodes.Const(None))
            if_ = nodes.If()
            if_.test = test
            if_.body = [nodes.Return()]  # placeholder for a control
            root.append(if_)

    return (
        get_token_count(root) + get_token_count(fun_def),
        get_statements_count(root, include_defs=False, include_name_main=True)
        + get_statements_count(fun_def, include_defs=False, include_name_main=True),
        (
            len(tests) + 1,
            get_statements_count(core, include_defs=False, include_name_main=True),
        ),
    )


### control functions


def duplicate_blocks_in_if(self, node: nodes.If) -> bool:
    if is_parents_elif(node):
        return False

    # do not break up consistent ifs
    if is_one_of_parents_ifs(node):
        return False

    ends_with_else, ifs = extract_from_elif(node)
    if not ends_with_else:
        return False

    if_bodies = get_bodies(ifs)
    assert len(if_bodies) >= 2
    result = antiunify(
        if_bodies,
        stop_on=lambda avars: length_mismatch(avars) or type_mismatch(avars),
        stop_on_after_renamed_identical=lambda avars: assignment_to_aunify_var(avars),
    )
    if result is None:
        return False
    core, avars = result

    if contains_other_duplication(core, avars):
        return False

    tokens_before = get_token_count(node)
    stmts_before = get_statements_count(node, include_defs=False, include_name_main=True)

    tests = [if_.test for if_ in ifs]
    called_avar = called_aunify_var(avars)
    tvs_change = test_variables_change(tests, core, avars)

    for fix_function in (
        get_fixed_by_restructuring_nested if not tvs_change else None,
        get_fixed_by_restructuring_twisted if not tvs_change else None,
        get_fixed_by_moving_if if not tvs_change else None,
        get_fixed_by_ternary if not called_avar and not tvs_change else None,
        get_fixed_by_vars if not called_avar else None,
        get_fixed_by_function if not called_avar else None,
    ):
        if fix_function is None:
            continue

        suggestion = fix_function(self, tests, core, avars)
        if suggestion is None:
            continue

        if not saves_enough_tokens(tokens_before, stmts_before, suggestion):
            continue

        message_id, _tokens, _statements, message_args = suggestion
        self.add_message(message_id, node=node, args=message_args)
        return True

    return False
