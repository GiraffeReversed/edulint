from collections import namedtuple
from functools import cached_property
from inspect import signature
from itertools import product
from typing import Tuple, List, Union, Optional

from astroid import nodes  # type: ignore
from astroid.const import Context

from edulint.linting.analyses.antiunify import (
    antiunify,
    cprint,  # noqa: F401
    get_sub_variant,
    contains_avar,
)
from edulint.linting.analyses.var_events import VarEventType
from edulint.linting.analyses.data_dependency import vars_in, is_changed_between
from edulint.linting.analyses.cfg.utils import get_cfg_loc
from edulint.linting.checkers.utils import (
    is_parents_elif,
    get_lines_between,
    get_statements_count,
    get_token_count,
    has_else_block,
    is_negation,
    are_identical,
    new_node,
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
    to_parent,
    get_common_parent,
    get_unique_avars,
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
        current = elif_

    if nested_count == 0 or nested_count >= len(result):
        return has_else_block(current), result
    return True, result[:-nested_count]


def get_bodies(ifs: List[nodes.If]) -> List[List[nodes.NodeNG]]:
    result = []
    for i, if_ in enumerate(ifs):
        result.append(if_.body)
        if i == len(ifs) - 1 and len(if_.orelse) > 0:
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
    root = new_node(nodes.If)
    if_ = root
    if_bodies = []
    for i, test in enumerate(tests):
        if_.test = test
        if_bodies.append(if_.body)
        if i != len(tests) - 1:
            elif_ = new_node(nodes.If)
            if_.orelse = [elif_]
            # elif_.parent = if_
            if_ = elif_
        else:
            if_bodies.append(if_.orelse)
    return root, if_bodies


### testing helper functions


def is_one_of_parents_ifs(node: nodes.If) -> bool:
    parent = node.parent
    if not isinstance(parent, nodes.If):
        return False

    while isinstance(parent.parent, nodes.If):
        parent = parent.parent

    _ends_with_else, ifs = extract_from_elif(parent)
    if_bodies = get_bodies(ifs)

    return all(any(isinstance(n, nodes.If) for n in body) for body in if_bodies)


def core_contains_other_duplication(core, avars) -> bool:
    parent = get_common_parent(avars)
    if parent is None:
        body = get_sub_variant(core, 0)
    elif isinstance(parent, (nodes.List, nodes.Tuple, nodes.Dict, nodes.Set)):
        body = list(get_sub_variant(parent, 0).get_children())
    else:
        return False

    return body_contains_other_duplication(body)


def body_contains_other_duplication(body) -> bool:
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


# def check_enabled(message_ids: Union[str, List[str]]):
#     if isinstance(message_ids, str):
#         message_ids = [message_ids]

#     def middle(func):
#         def inner(checker, *args, **kwargs):
#             if not any(checker.linter.is_message_enabled(mi) for mi in message_ids):
#                 return None
#             result = func(*args, **kwargs)
#             if result is None:
#                 return result

#             if len(message_ids) == 1:
#                 return Fixed(message_ids[0], *result)
#             symbol, *result = result
#             return Fixed(symbol, *result)

#         inner.__name__ = func.__name__
#         return inner

#     return middle


### identical code before/after branch


def identical_before_after_branch(
    checker, ifs: List[nodes.If], branches: List[List[nodes.NodeNG]]
) -> bool:

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

        checker.add_message(
            "identical-if-branches-part",
            node=defect_node,
            args=(lines_difference, "before" if forward else "after"),
        )

    any_message = False
    same_prefix_len = get_stmts_difference(branches, forward=True)
    if same_prefix_len >= 1:
        if all(same_prefix_len == len(b) for b in branches):
            checker.add_message("identical-if-branches", node=ifs[0])
            return True

        add_message(branches, same_prefix_len, ifs[0], forward=True)
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


def identical_seq_ifs(
    checker, ends_with_else: bool, ifs: List[nodes.If], seq_ifs: List[nodes.If]
) -> bool:

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

    if not ends_with_else:
        ifs = seq_ifs
        if ifs is None:
            return False
        symbol = "identical-seq-ifs"
    else:
        ifs = ifs
        symbol = "identical-seq-elifs"

    if len(ifs) == 1:
        return False

    i = 0
    last = None
    while i < len(ifs) - 1:
        count = same_ifs_count(ifs, i)
        if count > 1:
            first = ifs[i]
            assert isinstance(ifs[i + count - 1], nodes.If)
            last = ifs[i + count - 1].body[-1]

            checker.add_message(
                symbol,
                line=first.fromlineno,
                col_offset=first.col_offset,
                end_lineno=last.tolineno,
                end_col_offset=last.end_col_offset,
                args=(count,),
            )
        i += count

    return last is not None


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

    test = new_node(
        nodes.BoolOp,
        op="or",
        values=[
            new_node(nodes.BoolOp, op="and", values=[outer_test, inner_test]),
            new_node(
                nodes.BoolOp,
                op="and",
                values=[
                    new_node(nodes.UnaryOp, op="not", operand=outer_test),
                    new_node(nodes.UnaryOp, op="not", operand=inner_test),
                ],
            ),
        ],
    )

    if_ = new_node(
        nodes.If,
        test=test,
        body=inner_if.sub_locs[0].node.body,
        orelse=inner_if.sub_locs[0].node.orelse,
    )

    return if_


# @check_enabled("similar-if-to-untwisted")
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

    pos_inner_test = get_sub_variant(inner_test, 0)
    neg_inner_variant = get_sub_variant(inner_test, 1)

    if are_identical(pos_pos, neg_neg) and are_identical(pos_neg, neg_pos):
        neg_inner_test = new_node(nodes.UnaryOp, op="not", operand=neg_inner_variant)
    elif are_identical(pos_pos, neg_pos) and are_identical(pos_neg, neg_neg):
        neg_inner_test = neg_inner_variant
    else:
        return None

    test = new_node(
        nodes.BoolOp,
        op="or",
        values=[
            new_node(nodes.BoolOp, op="and", values=[outer_test, pos_inner_test]),
            new_node(
                nodes.BoolOp,
                op="and",
                values=[new_node(nodes.UnaryOp, op="not", operand=outer_test), neg_inner_test],
            ),
        ],
    )

    if_ = new_node(
        nodes.If,
        test=test,
        body=inner_if.sub_locs[0].node.body,
        orelse=inner_if.sub_locs[0].node.orelse,
    )

    return (
        get_token_count(if_),
        get_statements_count(if_, include_defs=False, include_name_main=False),
        (test.as_string(),),
    )


### if to use


# @check_enabled("similar-if-to-use")
def get_fixed_by_if_to_use(tests, core, avars):
    if len(tests) > 1 or len(avars) > 1:
        return None

    avar = avars[0]
    if (
        not isinstance(avar.parent, nodes.Const)
        or not isinstance(avar.subs[0], bool)
        or not isinstance(avar.subs[1], bool)
    ):
        return None

    # do not repeat simplifiable if
    if isinstance(avar.parent.parent, (nodes.Return, nodes.Assign)):
        return None

    return (
        get_token_count(core) - 1 + get_token_count(tests[0]),
        get_statements_count(core, include_defs=False, include_name_main=False),
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
                if has_parent_call or len(parent.args) > 1:
                    return True
                has_parent_call = True

            # if not isinstance(parent, SIMPLE_EXPRESSION_TYPES):
            if isinstance(parent, COMPLEX_EXPRESSION_TYPES):
                return True

            if hasattr(parent, "cfg_loc"):
                break

            parent = parent.parent

    return False


# @check_enabled("similar-if-to-expr")
def get_fixed_by_ternary(tests, core, avars):
    # the condition would get too complicated
    if len(tests) > 1 and any(isinstance(test, nodes.BoolOp) for test in tests):
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
            new = new_node(nodes.IfExp, test=test, body=to_node(avar_val, avar), orelse=expr)
            expr = new

        exprs.append(expr)

    return (
        get_token_count(core) - len(avars) + get_token_count(exprs),  # subtract aunify vars
        get_statements_count(core, include_defs=False, include_name_main=True),
        (exprs[0].as_string(),),
    )


### if into block

HEADER_ATTRIBUTES = {
    nodes.For: ["target", "iter"],
    nodes.While: ["test"],
    nodes.If: ["test"],
    nodes.ExceptHandler: ["name", "type"],
    nodes.Try: [],
    nodes.With: ["items"],
}

BODY_ATTRIBUTES = {
    nodes.For: ["body", "orelse"],
    nodes.While: ["body", "orelse"],
    nodes.If: ["body", "orelse"],
    nodes.ExceptHandler: ["body"],
    nodes.Try: ["body", "handlers", "orelse", "finalbody"],
    nodes.With: ["body"],
}


def if_can_be_moved(core, avars):
    if type(core) not in HEADER_ATTRIBUTES.keys():
        return False

    # avar in header
    if any(contains_avar(getattr(core, attr), avars) for attr in HEADER_ATTRIBUTES[type(core)]):
        return False

    return (
        sum(contains_avar(getattr(core, attr), avars) for attr in BODY_ATTRIBUTES[type(core)]) == 1
    )


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
            root, lines = get_fixed_by_moving_if_rec(tests, core[min_], avars)
        else:
            new_body = core[min_ : max_ + 1]
            root, if_bodies = create_ifs(tests)
            for if_body in if_bodies:
                if_body.extend(new_body)
            lines = [
                (new_body[0].sub_locs[i].node.fromlineno, new_body[-1].sub_locs[i].node.tolineno)
                for i in range(len(new_body[0].sub_locs))
            ]
            lines = [f"{start}" if start == end else f"{start}-{end}" for start, end in lines]

        return core[:min_] + [root] + core[max_ + 1 :], lines

    assert contains_avar(core, avars) and if_can_be_moved(core, avars)
    new_core = new_node(type(core))

    for attr in HEADER_ATTRIBUTES[type(core)]:
        setattr(new_core, attr, getattr(core, attr))

    lines = []
    for attr in BODY_ATTRIBUTES[type(core)]:
        attrval = getattr(core, attr)
        if contains_avar(attrval, avars):
            new_body, sublines = get_fixed_by_moving_if_rec(tests, getattr(core, attr), avars)
            lines.extend(sublines)
        else:
            new_body = attrval
        setattr(new_core, attr, new_body)

    return new_core, lines


# @check_enabled("similar-if-into-block")
def get_fixed_by_moving_if(tests, core, avars):
    # too restrictive -- the change may be before the avar but after the place
    # where the if would be inserted
    if (not isinstance(core, list) and not if_can_be_moved(core, avars)) or (
        isinstance(core, list) and not if_can_be_moved(core[0], avars)
    ):
        return None

    fixed, lines = get_fixed_by_moving_if_rec(tests, core, avars)
    return (
        get_token_count(fixed)
        + sum(
            get_token_count(v) if isinstance(v, nodes.NodeNG) else 0
            for avar in avars
            for v in avar.subs
        ),
        get_statements_count(fixed, include_defs=True, include_name_main=False),
        (", ".join(lines),),
    )


### if to variables


# @check_enabled("similar-if-to-extracted")
def get_fixed_by_vars(tests, core, avars):
    root, if_bodies = create_ifs(tests)
    for avar in get_unique_avars(avars):

        for val, body in zip(avar.subs, if_bodies):
            assign = new_node(nodes.Assign)
            assign.targets = [new_node(nodes.AssignName, name=avar.name)]
            assign.value = to_node(val, avar)
            body.append(assign)

    return (
        get_token_count(root) + get_token_count(core),
        get_statements_count(root, include_defs=False, include_name_main=True)
        + get_statements_count(core, include_defs=False, include_name_main=True),
        (),
    )


### if to container


def get_simple_val(val: nodes.NodeNG, toplevel) -> Optional[Union[nodes.Name, nodes.Const]]:
    if toplevel or not isinstance(val, (nodes.Name, nodes.Const)):
        return None
    return val


def vals_from_simple_test(
    test, toplevel=True
) -> Optional[List[List[Tuple[nodes.Name, nodes.Const]]]]:
    if isinstance(test, nodes.Compare):
        if len(test.ops) != 1 or test.ops[0][0] != "==":
            return None
        lt = get_simple_val(test.left, toplevel=False)
        rt = get_simple_val(test.ops[0][1], toplevel=False)
        if lt is None or rt is None:
            return None
        if isinstance(lt, nodes.Name) and isinstance(rt, nodes.Const):
            return [[(lt, rt)]]
        if isinstance(rt, nodes.Name) and isinstance(lt, nodes.Const):
            return [[(rt, lt)]]
        return None

    if isinstance(test, nodes.BoolOp):
        if test.op not in ("and", "or"):
            return None
        partitions = []
        for operand in test.values:
            vals = vals_from_simple_test(operand)
            if vals is None:
                return None
            partitions.append(vals)
        if test.op == "or":
            return [part for partition in partitions for part in partition]
        else:
            return [
                sorted([pair for part in partition for pair in part], key=lambda pair: pair[0].name)
                for partition in product(*partitions)
            ]

    return get_simple_val(test, toplevel)


def get_node_fixed_by_container(core, avars, tests_propositions, has_else_block):
    container_values = []
    for i in range(len(tests_propositions)):
        for _ in tests_propositions[i]:
            if len(avars) == 1:
                new_item = new_node(nodes.Const, value=avars[0].subs[i])
            else:
                new_item = new_node(
                    nodes.Tuple,
                    elts=[new_node(nodes.Const, value=avar.subs[i]) for avar in avars],
                )
            container_values.append(new_item)

    if len(tests_propositions[0][0]) == 1 and sorted(
        test_proposition[0][1].value
        for test_propositions in tests_propositions
        for test_proposition in test_propositions
    ) == list(range(sum(len(test_propositions) for test_propositions in tests_propositions))):
        container = new_node(nodes.List, elts=container_values)
    else:
        dict_items = []
        value_index = 0
        for test_propositions in tests_propositions:
            for test_proposition in test_propositions:
                test_propositions = tests_propositions[i]

                if len(test_proposition) == 1:
                    key = new_node(nodes.Const, value=test_proposition[0][1].value)
                else:
                    key = new_node(
                        nodes.Tuple,
                        elts=[
                            new_node(nodes.Const, value=pair[1].value) for pair in test_proposition
                        ],
                    )

                val = container_values[value_index]
                value_index += 1

                dict_items.append((key, val))

        container = new_node(nodes.Dict, items=dict_items)

    assignment = new_node(
        nodes.Assign, targets=[new_node(nodes.AssignName, name="CONTAINER")], value=container
    )
    variables = [pair[0].name for pair in tests_propositions[0][0]]
    var_tuple = (
        new_node(nodes.Name, name=variables[0])
        if len(variables) == 1
        else new_node(nodes.Tuple, elts=[new_node(nodes.Name, name=name) for name in variables])
    )

    if_ = new_node(
        nodes.If,
        test=new_node(
            nodes.Compare,
            left=var_tuple,
            ops=[("in", new_node(nodes.Name, name="CONTAINER"))],
        ),
        body=(core if isinstance(core, list) else [core])
        + [
            new_node(
                nodes.Subscript,
                value=new_node(nodes.Name, name="CONTAINER"),
                slice=var_tuple,
                ctx=Context.Load,
            )
        ],
        orelse=[] if not has_else_block else core if isinstance(core, list) else [core],
    )

    return "similar-if-to-" + ("list" if isinstance(container, nodes.List) else "dict"), [
        assignment,
        if_,
    ]


def get_fixed_by_container(checker, seq_ifs, has_else_block):
    tests_propositions = [vals_from_simple_test(if_.test) for if_ in seq_ifs]
    start_index = 0
    end_index = 0
    inc_start = True
    for i in range(len(tests_propositions)):
        if inc_start:
            if tests_propositions[i] is None:
                start_index += 1
            else:
                inc_start = False
                end_index = start_index
        else:
            if tests_propositions[i] is None:
                break
            else:
                end_index += 1

    if end_index - start_index + 1 < 3 or (
        start_index != 0 and end_index != len(tests_propositions) - 1
    ):
        return False
    tests_propositions = tests_propositions[start_index : end_index + 1]
    ifs = seq_ifs[start_index : end_index + 1]

    for test_propositions in tests_propositions:
        for test_proposition in test_propositions:
            if len(test_proposition) != len(tests_propositions[0][0]):
                return False
            for i in range(len(test_proposition)):
                if test_proposition[i][0].name != tests_propositions[0][0][i][0].name:
                    return False

    if_bodies = [if_.body for if_ in ifs] + ([ifs[-1].orelse] if has_else_block else [])
    result = antiunify(
        if_bodies,
        stop_on=lambda avars: length_mismatch(avars) or type_mismatch(avars),
        stop_on_after_renamed_identical=lambda avars: assignment_to_aunify_var(avars),
    )
    if result is None:
        return False
    core, avars = result
    avars = list(get_unique_avars(avars))
    if (
        len(avars) > 2
        or core_contains_other_duplication(core, avars)
        or called_aunify_var(avars)
        or test_variables_change([if_.test for if_ in ifs], core, avars)
    ):
        return False

    symbol, fixed = get_node_fixed_by_container(core, avars, tests_propositions, has_else_block)

    tokens_before = (
        sum(get_token_count(body) for body in if_bodies)
        + sum(get_token_count(if_.test) for if_ in ifs)
        + len(ifs)
        + (1 if has_else_block else 0)
    )
    stmts_before = (
        get_statements_count(if_bodies, include_defs=False, include_name_main=True)
        + len(ifs)
        + (1 if has_else_block else 0)
    )
    # subtract 1 as subscript is not a part of the core and adds one statement and one token
    tokens_after = get_token_count(fixed) - 1
    stmts_after = get_statements_count(fixed, include_defs=False, include_name_main=True) - 1

    if saves_enough_tokens(tokens_before, stmts_before, tokens_after, stmts_after):
        checker.add_message(
            symbol,
            line=ifs[0].fromlineno,
            col_offset=ifs[0].col_offset,
            end_lineno=ifs[-1].tolineno,
            end_col_offset=ifs[-1].end_col_offset,
        )


### structure cache


class IfStructures:
    def __init__(self, checker, if_: nodes.If):
        self.checker = checker
        self.if_ = if_

    @cached_property
    def _ends_with_else_ifs(self):
        return extract_from_elif(self.if_)

    @property
    def ends_with_else(self):
        return self._ends_with_else_ifs[0]

    @property
    def ifs(self):
        return self._ends_with_else_ifs[1]

    @cached_property
    def branches(self):
        return get_bodies(self.ifs)

    @cached_property
    def seq_ifs(self):
        prev_sibling = self.ifs[0].previous_sibling()
        if isinstance(prev_sibling, nodes.If) and not extract_from_elif(prev_sibling)[0]:
            return None

        seq_ifs = self.ifs.copy()
        extract_from_siblings(seq_ifs[0], seq_ifs)
        return seq_ifs

    @cached_property
    def is_one_of_parents_ifs(self):
        return is_one_of_parents_ifs(self.ifs[0])

    @cached_property
    def core_avars(self):
        return antiunify(
            self.branches,
            stop_on=lambda avars: length_mismatch(avars) or type_mismatch(avars),
            stop_on_after_renamed_identical=lambda avars: assignment_to_aunify_var(avars),
        )

    @property
    def core(self):
        return self.core_avars[0] if self.core_avars is not None else None

    @property
    def avars(self):
        return self.core_avars[1] if self.core_avars is not None else None

    @cached_property
    def core_contains_other_duplication(self):
        return core_contains_other_duplication(self.core, self.avars)

    @cached_property
    def tokens_before(self):
        return get_token_count(self.ifs[0])

    @cached_property
    def stmts_before(self):
        return get_statements_count(self.ifs[0], include_defs=False, include_name_main=True)

    @cached_property
    def tests(self):
        return [if_.test for if_ in self.ifs]

    @cached_property
    def called_avar(self):
        return called_aunify_var(self.avars)

    @cached_property
    def tvs_change(self):
        return test_variables_change(self.tests, self.core, self.avars)

    @cached_property
    def shared_for_similar(self):
        return (
            self.ends_with_else
            and not self.is_one_of_parents_ifs  # do not break up consistent ifs
            and self.core is not None
            and not self.core_contains_other_duplication
        )

    def eval(self, f):
        return f(*[getattr(self, name) for name in signature(f).parameters.keys()])


### control functions

FixAttempt = namedtuple(
    "FixAttempt",
    [
        "symbols",
        "should_run",
        "fix_function",
        "args",
        "postprocess",
        "check_message_enabled",
        "check_first_body",
    ],
)


def fixes_and_saves_enough_tokens(
    checker, tokens_before, stmts_before, ifs, symbols, result, min_saved_ratio
):
    if result is None:
        return False

    if len(symbols) == 1:
        suggestion = Fixed(symbols[0], *result)
    else:
        symbol, *result = result
        suggestion = Fixed(symbol, *result)

    if not saves_enough_tokens(
        tokens_before, stmts_before, suggestion.tokens, suggestion.statements, min_saved_ratio
    ):
        return False

    checker.add_message(suggestion.symbol, node=ifs[0], args=suggestion.message_args)
    return True


def emit_message_if(checker, symbols, node, result: bool):
    assert len(symbols) == 1
    if result:
        checker.add_message(symbols[0], node=node)
    return result


def duplicate_in_if(checker, node: nodes.If) -> Tuple[bool, bool]:
    if is_parents_elif(node):
        return False, False

    structs = IfStructures(checker, node)

    for fix_attempt in (
        FixAttempt(
            ["identical-if-branches-part"],
            structs.ends_with_else,
            identical_before_after_branch,
            (checker, structs.ifs, structs.branches),
            postprocess=lambda _symbols, result: result,
            check_message_enabled=False,
            check_first_body=True,
        ),
        FixAttempt(
            ["identical-seq-ifs", "identical-seq-elifs"],
            True,
            identical_seq_ifs,
            (checker, structs.ends_with_else, structs.ifs, structs.seq_ifs),
            postprocess=lambda _symbols, result: result,
            check_message_enabled=False,
            check_first_body=True,
        ),
        FixAttempt(
            ["identical-if-branches"],
            structs.shared_for_similar,
            lambda avars: len(avars) == 0,
            (structs.avars,),
            postprocess=lambda symbols, result: emit_message_if(
                checker, symbols, structs.ifs[0], result
            ),
            check_message_enabled=False,
            check_first_body=False,
        ),
        FixAttempt(
            ["similar-if-to-untwisted"],
            structs.shared_for_similar and not structs.tvs_change,
            get_fixed_by_restructuring_twisted,
            (structs.tests, structs.core, structs.avars),
            lambda symbols, result: fixes_and_saves_enough_tokens(
                checker,
                structs.tokens_before,
                structs.stmts_before,
                structs.ifs,
                symbols,
                result,
                min_saved_ratio=0,
            ),
            check_message_enabled=True,
            check_first_body=False,
        ),
        FixAttempt(
            ["similar-if-to-use"],
            structs.shared_for_similar and not structs.tvs_change,
            get_fixed_by_if_to_use,
            (structs.tests, structs.core, structs.avars),
            lambda symbols, result: fixes_and_saves_enough_tokens(
                checker,
                structs.tokens_before,
                structs.stmts_before,
                structs.ifs,
                symbols,
                result,
                min_saved_ratio=0,
            ),
            check_message_enabled=True,
            check_first_body=False,
        ),
        FixAttempt(
            ["similar-if-into-block"],
            structs.shared_for_similar and not structs.tvs_change,
            get_fixed_by_moving_if,
            (structs.tests, structs.core, structs.avars),
            lambda symbols, result: fixes_and_saves_enough_tokens(
                checker,
                structs.tokens_before,
                structs.stmts_before,
                structs.ifs,
                symbols,
                result,
                min_saved_ratio=0,
            ),
            check_message_enabled=True,
            check_first_body=False,
        ),
        FixAttempt(
            ["similar-if-to-list", "similar-if-to-dict"],
            # not structs.is_one_of_parents_ifs and not structs.contains_other_duplication,
            not structs.is_one_of_parents_ifs  # do not break up consistent ifs
            and structs.seq_ifs is not None,
            get_fixed_by_container,
            (checker, structs.seq_ifs, structs.ends_with_else),
            lambda symbols, result: result,
            check_message_enabled=True,
            check_first_body=False,
        ),
        FixAttempt(
            ["similar-if-to-expr"],
            structs.shared_for_similar and not structs.tvs_change and not structs.called_avar,
            get_fixed_by_ternary,
            (structs.tests, structs.core, structs.avars),
            lambda symbols, result: fixes_and_saves_enough_tokens(
                checker,
                structs.tokens_before,
                structs.stmts_before,
                structs.ifs,
                symbols,
                result,
                min_saved_ratio=0.2,
            ),
            check_message_enabled=True,
            check_first_body=False,
        ),
        FixAttempt(
            ["similar-if-to-extracted"],
            structs.shared_for_similar and not structs.called_avar,
            get_fixed_by_vars,
            (structs.tests, structs.core, structs.avars),
            lambda symbols, result: fixes_and_saves_enough_tokens(
                checker,
                structs.tokens_before,
                structs.stmts_before,
                structs.ifs,
                symbols,
                result,
                min_saved_ratio=0.2,
            ),
            check_message_enabled=True,
            check_first_body=False,
        ),
    ):
        if (
            (
                not fix_attempt.check_message_enabled
                or any(checker.linter.is_message_enabled(symbol) for symbol in fix_attempt.symbols)
            )
            and fix_attempt.should_run
            and fix_attempt.postprocess(
                fix_attempt.symbols, fix_attempt.fix_function(*fix_attempt.args)
            )
        ):
            return True, fix_attempt.check_first_body

    return False, False
