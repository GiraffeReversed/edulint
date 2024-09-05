from typing import List

from astroid import nodes  # type: ignore

from edulint.linting.analyses.antiunify import (
    antiunify,
    core_as_string,
    new_node,
    cprint,  # noqa: F401
)
from edulint.linting.analyses.data_dependency import vars_in
from edulint.linting.checkers.utils import (
    get_statements_count,
    get_token_count,
    get_range_params,
    get_const_value,
)
from edulint.linting.checkers.duplication.utils import (
    Fixed,
    length_mismatch,
    type_mismatch,
    called_aunify_var,
    assignment_to_aunify_var,
    saves_enough_tokens,
    to_node,
    to_start_lines,
)


class NoSubseqToLoop(Exception):
    pass


### constructive helper functions


def to_range_args(sequence):
    start = None
    step = None
    previous = None
    for s in sequence:
        if not isinstance(s, int):
            return None
        if start is None:
            start = s
        elif step is None:
            step = s - start
        else:
            assert previous is not None
            if s - previous != step:
                return None
        previous = s

    return (start, previous + (1 if step > 0 else -1), step)


def to_range_node(range_args):
    start, stop, step = range_args

    range_ = new_node(nodes.Call, func=new_node(nodes.Name, name="range"))
    start_node = new_node(nodes.Const, value=start)
    stop_node = new_node(nodes.Const, value=stop)
    step_node = new_node(nodes.Const, value=step)
    if step != 1:
        range_.args = [start_node, stop_node, step_node]
    elif start != 0:
        range_.args = [start_node, stop_node]
    else:
        range_.args = [stop_node]
    return range_


### nice sequence helpers


def partition_by_type(sequence):
    result = []
    current = []

    for n in sequence:
        if len(current) == 0 or isinstance(n, type(current[-1])):
            current.append(n)
        else:
            result.append(current)
            current = [n]

    if len(current) > 0:
        result.append(current)

    return result


def to_const_sequence(sequence):
    result = []
    for v in sequence:
        c = get_const_value(v)
        if c is None:
            return None
        result.append(c)
    return result


def from_chars(avar, sequence):
    if not isinstance(avar.parent, nodes.Const):
        return None

    if not all(isinstance(s, str) and len(s) == 1 for s in sequence):
        return None

    min_char = min(sequence)

    sequence = [ord(s) - ord(min_char) for s in sequence]

    if ord(min_char) == 0:
        return sequence, avar

    # chr(ord(min_char) + ID)
    ord_call = new_node(
        nodes.Call,
        func=new_node(nodes.Name, name="ord"),
        args=[new_node(nodes.Const, value=min_char)],
    )

    binop = new_node(nodes.BinOp, op="+", left=ord_call, right=avar)

    chr_call = new_node(nodes.Call, func=new_node(nodes.Name, name="chr"), args=[binop])

    return sequence, chr_call


def iter_use_from_partition(partition):
    types = [type(p[0]) for p in partition]
    # a type repeats
    if len(types) != len(set(types)):
        return None

    exclusive = set(types) & {nodes.Name, nodes.Subscript, nodes.Attribute}
    # different exclusive types or an exclusive type multiple times
    if len(exclusive) > 1:
        return None

    type_groups = {type(p[0]): p for p in partition}
    for t in (nodes.Const, nodes.Name, nodes.Subscript, nodes.Attribute, nodes.BinOp):
        type_groups[t] = type_groups.get(t, [])

    # multiple constants or no binops
    if len(type_groups[nodes.Const]) > 1 or len(type_groups[nodes.BinOp]) == 0:
        return None

    if len(exclusive) == 1:
        exclusive_type = next(iter(exclusive))
        # multiple values for an exclusive type
        if len(type_groups[exclusive_type]) > 1:
            return None
        exclusive_value = type_groups[exclusive_type][0]
    else:
        exclusive_type = None
        exclusive_value = None

    if not any(
        ts
        in (
            [nodes.Const, exclusive_type, nodes.BinOp],
            [exclusive_type, nodes.BinOp],
            [nodes.Const, nodes.BinOp],
        )
        for ts in (types, list(reversed(types)))
    ):
        return None

    binop_core, bionp_avars = antiunify(type_groups[nodes.BinOp])
    assert isinstance(binop_core, nodes.BinOp)
    # all same binops and binops differing in multiple places break niceness
    if len(bionp_avars) != 1 or called_aunify_var(bionp_avars):
        return None
    binop_avar = bionp_avars[0]

    if len(type_groups[nodes.Const]) == 1:
        const_value = type_groups[nodes.Const][0]
    else:
        const_value = None

    # no child is related to the shared value
    if (
        exclusive_value is not None
        and binop_core.right.as_string() != exclusive_value.as_string()
        and binop_core.left.as_string() != exclusive_value.as_string()
    ) or (
        exclusive_value is None
        and const_value is not None
        and core_as_string(binop_core.right) != const_value.as_string()
        and core_as_string(binop_core.left) != const_value.as_string()
    ):
        return None

    if const_value is not None:
        const_nums = [0]
    else:
        const_nums = []

    if exclusive_value is not None:
        if binop_core.op == "+" or (
            binop_core.op == "-" and exclusive_value.as_string() == binop_core.left.as_string()
        ):
            exclusive_nums = [0]
        elif binop_core.op == "*" or (
            binop_core.op in ("/", "//", "%")
            and exclusive_value.as_string() == binop_core.left.as_string()
        ):
            exclusive_nums = [1]
        else:
            exclusive_nums = []
    else:
        exclusive_nums = []

    if isinstance(binop_avar.subs[0], nodes.NodeNG):
        binop_result = iter_use_from_partition(partition_by_type(binop_avar.subs))
        if binop_result is None:
            return None
        binop_nums, sub_binop_use = binop_result
        if binop_core.left == binop_avar.parent:
            binop_core.left = sub_binop_use
        else:
            binop_core.right = sub_binop_use
    else:
        binop_nums = binop_avar.subs

    dct = {
        nodes.Const: const_nums,
        exclusive_type: exclusive_nums,
        nodes.BinOp: binop_nums,
    }

    return [n for t in types for n in dct[t]], binop_core


def to_iter_use(avar):
    sequence = list(avar.subs)
    use = avar

    const_sequence = to_const_sequence(sequence)
    if const_sequence is not None:
        sequence = const_sequence

    from_chars_result = from_chars(avar, sequence)
    if from_chars_result is not None:
        sequence, use = from_chars_result

    range_args = to_range_args(sequence)
    if range_args is not None:
        return range_args, use

    partition = partition_by_type(sequence)
    # single type present => use values directly, if different
    if len(partition) == 1:
        assert not any(isinstance(v, nodes.NodeNG) for v in sequence)
        if len(sequence) != len(set(sequence)):  # some value is repeated
            return None
        return sequence, use

    result = iter_use_from_partition(partition)
    if result is None:
        return None
    range_nums, use = result
    range_args = to_range_args(range_nums)
    if range_args is None:
        return None
    return range_args, use


def consolidate_ranges(ranges):
    if len(ranges) == 1:
        range_args, use = ranges[0]
        return [to_range_node(range_args)], [use]

    uses = []
    for (start, stop, step), use in ranges:
        if step != 1:
            use = new_node(nodes.BinOp, op="*", left=use, right=new_node(nodes.Const, value=step))
        if start != 0:
            use = new_node(nodes.BinOp, op="+", left=use, right=new_node(nodes.Const, value=start))
        uses.append(use)

    start, stop, step = 0, (stop - start - 1) // step + 1, 1
    return [to_range_node((start, stop, step))], uses


def get_nice_iters(avars, to_aunify):
    sequences = [avar.subs for avar in avars]
    if len(sequences) == 0:
        range_node = new_node(
            nodes.Call,
            func=new_node(nodes.Name, name="range"),
            args=[new_node(nodes.Const, value=len(to_aunify))],
        )
        return [range_node], {}

    iter_uses = []
    for avar in avars:
        result = to_iter_use(avar)
        if result is None:
            return None
        iter, use = result
        iter_uses.append((iter, use))

    ranges = [(iter, use) for iter, use in iter_uses if isinstance(iter, tuple)]

    # disallow mixing ranges with collections
    # TODO maybe too strict?
    if len(ranges) != 0 and len(ranges) != len(iter_uses):
        return None

    if len(ranges) == 0:
        str_iters = {
            tuple(to_node(n, avars[i]).as_string() for n in iter)
            for i, (iter, _use) in enumerate(iter_uses)
        }
        if len(str_iters) != 1:
            return None
        some_iter, use = iter_uses[0]
        if isinstance(use, nodes.Call) and use.func.name == "chr":
            start = use.args[0].left.args[0].value
            some_iter = [chr(ord(start) + v) for v in some_iter]

        collection = new_node(nodes.List, elts=[to_node(n, avars[0]) for n in some_iter])
        return [collection], [use for _iter, use in iter_uses]

    if len({r[0] for r in ranges}) > 2:
        raise NoSubseqToLoop

    return consolidate_ranges(ranges)


### fixers


def get_iter(iters):
    return iters[0]


def get_target(_avars, _iters):
    return new_node(nodes.AssignName, name="i")


def get_fixed_by_merging_with_parent_loop(to_aunify, core, avars):
    parent = to_aunify[0][0].parent
    if len(avars) > 0 or not isinstance(parent, nodes.For):
        return None

    first = to_aunify[0][0]
    last = to_aunify[-1][-1]

    if first != parent.body[0] or last != parent.body[-1]:
        return None

    range_params = get_range_params(parent.iter)
    if range_params is None:
        return None

    start, stop, step = range_params
    if get_const_value(start) != 0 or get_const_value(step) != 1:
        return None

    used_vars = vars_in([n for ns in to_aunify for n in ns])
    target = parent.target
    # TODO can be weakened -- use div to get i's original value
    if (
        not isinstance(target, nodes.AssignName)
        or (target.name, parent.scope()) in used_vars.keys()
    ):
        return None

    const_stop = get_const_value(stop)
    new_iter = (
        f"{const_stop * len(to_aunify)}"
        if isinstance(stop, nodes.Const)
        else f"{stop.as_string()} * {len(to_aunify)}"
    )
    return Fixed(
        "similar-block-to-loop-merge",
        get_token_count(core),
        get_statements_count(core, include_defs=False, include_name_main=True),
        (to_start_lines(to_aunify), new_iter),
    )


def get_fixed_by_loop(to_aunify, core, avars):
    result = get_nice_iters(avars, to_aunify)
    if result is None:
        return None
    iters, uses = result
    assert len(iters) == 1

    iterable = get_iter(iters)
    for_ = new_node(nodes.For, iter=iterable, target=get_target(avars, iters), body=core)

    symbol = (
        "similar-block-to-loop-range"
        if isinstance(iterable, nodes.Call)
        else "similar-block-to-loop-collection"
    )

    return Fixed(
        symbol,
        get_token_count(for_),
        get_statements_count(for_, include_defs=False, include_name_main=True),
        (
            len(to_aunify),
            get_statements_count(to_aunify[0], include_defs=False, include_name_main=True),
            iterable.as_string(),
        ),
    )


### control function


def similar_to_loop(self, to_aunify: List[List[nodes.NodeNG]]) -> bool:
    if max(len(to_aunify), len(to_aunify[0])) <= 2:  # TODO parametrize?
        return False

    result = antiunify(
        to_aunify,
        stop_on=lambda avars: length_mismatch(avars)
        or type_mismatch(
            avars,
            allowed_mismatches=[
                {nodes.Const, nodes.BinOp, t}
                for t in (nodes.Name, nodes.Subscript, nodes.Attribute)
            ],
        )
        or called_aunify_var(avars),
        stop_on_after_renamed_identical=lambda avars: assignment_to_aunify_var(avars),
    )
    if result is None:
        return False
    core, avars = result

    tokens_before = sum(get_token_count(node) for node in to_aunify)
    stmts_before = sum(
        get_statements_count(node, include_defs=False, include_name_main=True) for node in to_aunify
    )

    fixed_by_merge = get_fixed_by_merging_with_parent_loop(to_aunify, core, avars)
    if fixed_by_merge is not None:
        fixed = fixed_by_merge
    else:
        try:
            fixed = get_fixed_by_loop(to_aunify, core, avars)
        except NoSubseqToLoop:
            return True

        if fixed is None:
            return False

    if not saves_enough_tokens(tokens_before, stmts_before, fixed):
        return False

    message_id, _tokens, _statements, message_args = fixed

    first = to_aunify[0][0]
    last = to_aunify[-1][-1]
    self.add_message(
        message_id,
        line=first.fromlineno,
        col_offset=first.col_offset,
        end_lineno=last.tolineno,
        end_col_offset=last.col_offset,
        args=message_args,
    )
    return True
