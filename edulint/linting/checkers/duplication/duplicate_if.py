from collections import namedtuple
from functools import cached_property
from inspect import signature
from typing import Tuple, List

from astroid import nodes  # type: ignore

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


def contains_other_duplication(core, avars) -> bool:
    parent = get_common_parent(avars)
    if parent is None:
        body = get_sub_variant(core, 0)
    elif isinstance(parent, (nodes.List, nodes.Tuple, nodes.Dict, nodes.Set)):
        body = list(get_sub_variant(parent, 0).get_children())
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

    inner_test_variant = get_sub_variant(inner_test, 0)
    pp_test = new_node(nodes.BoolOp, op="and", values=[outer_test, inner_test_variant])

    neg_outer_test = new_node(nodes.UnaryOp, op="not", operand=outer_test)
    neg_inner_test = new_node(nodes.UnaryOp, op="not", operand=inner_test_variant)

    nn_test = new_node(nodes.BoolOp, op="and", values=[neg_outer_test, neg_inner_test])

    test = new_node(nodes.BoolOp, op="or", values=[pp_test, nn_test])

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
    seen = {}
    for avar in avars:
        var_vals = tuple(avar.subs)
        varname = seen.get(var_vals, avar.name)

        if varname != avar.name:
            continue
        seen[var_vals] = avar.name

        for val, body in zip(var_vals, if_bodies):
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
    def contains_other_duplication(self):
        return contains_other_duplication(self.core, self.avars)

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
            and not self.contains_other_duplication
        )

    def eval(self, f):
        return f(*[getattr(self, name) for name in signature(f).parameters.keys()])


# class IfStructures:
#     def __init__(self, checker, if_: nodes.If):
#         self.checker = checker
#         self.if_ = if_

#         self.ends_with_else, self.ifs = extract_from_elif(if_)
#         self.tests = [if_.test for if_ in self.ifs]
#         self.branches = get_bodies(self.ifs)

#         prev_sibling = self.ifs[0].previous_sibling()
#         if isinstance(prev_sibling, nodes.If) and not extract_from_elif(prev_sibling)[0]:
#             self.seq_ifs = None
#         else:
#             self.seq_ifs = self.ifs.copy()
#             extract_from_siblings(self.seq_ifs[0], self.seq_ifs)

#         self.tokens_before = get_token_count(self.ifs[0])
#         self.stmts_before = get_statements_count(
#             self.ifs[0], include_defs=False, include_name_main=True
#         )

#         self.is_one_of_parents_ifs = is_one_of_parents_ifs(self.ifs[0])

#         result = antiunify(
#             self.branches,
#             stop_on=lambda avars: length_mismatch(avars) or type_mismatch(avars),
#             stop_on_after_renamed_identical=lambda avars: assignment_to_aunify_var(avars),
#         )
#         if result is not None:
#             self.core, self.avars = result
#             self.contains_other_duplication = contains_other_duplication(self.core, self.avars)
#             self.called_avar = called_aunify_var(self.avars)
#             self.tvs_change = test_variables_change(self.tests, self.core, self.avars)
#         else:
#             self.core, self.avars = None, None

#         self.shared_for_similar = (
#             self.ends_with_else
#             and not self.is_one_of_parents_ifs  # do not break up consistent ifs
#             and self.core is not None
#             and not self.contains_other_duplication
#         )


def similar_blocks_in_if(checker, structs: IfStructures) -> bool:
    if not structs.ends_with_else:
        return False

    # do not break up consistent ifs
    if is_one_of_parents_ifs(structs.ifs[0]):
        return False

    if_bodies = structs.branches
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

    if len(avars) == 0:
        checker.add_message("identical-if-branches", node=structs.ifs[0])
        return True

    tokens_before = get_token_count(structs.ifs[0])
    stmts_before = get_statements_count(structs.ifs[0], include_defs=False, include_name_main=True)

    tests = [if_.test for if_ in structs.ifs]
    called_avar = called_aunify_var(avars)
    tvs_change = test_variables_change(tests, core, avars)

    # tests = [if_.test for if_ in ifs]
    # called_avar = called_aunify_var(avars)
    # tvs_change = test_variables_change(tests, core, avars)

    # tokens_before = (
    #     sum(get_token_count(body) for body in if_bodies)
    #     + get_token_count(tests)
    #     + len(tests)
    #     + (1 if ends_with_else else 0)
    # )
    # stmts_before = (
    #     get_statements_count(if_bodies, include_defs=False, include_name_main=True)
    #     + len(tests)
    #     + (1 if ends_with_else else 0)
    # )

    for fix_function in (
        get_fixed_by_restructuring_twisted if not tvs_change else None,
        get_fixed_by_if_to_use if not tvs_change else None,
        get_fixed_by_moving_if if not tvs_change else None,
        get_fixed_by_ternary if not called_avar and not tvs_change else None,
        get_fixed_by_vars if not called_avar else None,
    ):
        if fix_function is None:
            continue

        suggestion = fix_function(checker, tests, core, avars)
        if suggestion is None:
            continue

        if not saves_enough_tokens(tokens_before, stmts_before, suggestion):
            continue

        message_id, _tokens, _statements, message_args = suggestion
        checker.add_message(message_id, node=structs.ifs[0], args=message_args)
        return True

    return False


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

    if not saves_enough_tokens(tokens_before, stmts_before, suggestion, min_saved_ratio):
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
