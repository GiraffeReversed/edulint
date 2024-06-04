from collections import namedtuple
from typing import Tuple, List, Generator

from astroid import nodes

from edulint.linting.analyses.antiunify import cprint  # noqa: F401


Fixed = namedtuple("Fixed", ["symbol", "tokens", "statements", "message_args"])


### antiunification conditions


def length_mismatch(avars) -> bool:
    for avar in avars:
        some = avar.subs[0]
        if not isinstance(some, list) and any(isinstance(sub, list) for sub in avar.subs):
            return True
        if isinstance(some, list) and any(len(sub) != len(some) for sub in avar.subs):
            return True
    return False


def type_mismatch(avars, allowed_mismatches=None) -> bool:
    allowed_mismatches = allowed_mismatches if allowed_mismatches is not None else []
    for avar in avars:
        sub_types = {type(sub) for sub in avar.subs}
        if any(sub_types.issubset(am) for am in allowed_mismatches):
            continue
        if len(sub_types) > 1:
            return True
    return False


def called_aunify_var(avars) -> bool:
    for avar in avars:
        node = avar.parent
        if (
            (isinstance(node, nodes.Compare) and avar in [o for o, n in node.ops])
            or (isinstance(node, nodes.BinOp) and avar == node.op)
            or (isinstance(node, nodes.AugAssign) and avar == node.op)
            or (isinstance(node, nodes.Attribute) and avar == node.attrname)
        ):
            return True

        while node is not None:
            if isinstance(node.parent, nodes.Call) and node == node.parent.func:
                return True
            node = node.parent
    return False


def assignment_to_aunify_var(avars) -> bool:
    return any(isinstance(avar.parent, (nodes.AssignName, nodes.AssignAttr)) for avar in avars)


### general


def is_duplication_candidate(stmtss) -> bool:
    for ns in zip(*stmtss):
        if not all(isinstance(n, type(ns[0])) for n in ns):
            return False
    return True


def saves_enough_tokens(tokens_before: int, stmts_before: int, fixed: Fixed):
    if fixed.symbol in ("nested-if-to-restructured", "twisted-if-to-restructured", "if-into-block"):
        return True
    return fixed.statements <= stmts_before and fixed.tokens < 0.8 * tokens_before


def get_loop_repetitions(
    block: List[nodes.NodeNG],
) -> Generator[Tuple[int, List[List[nodes.NodeNG]]], None, None]:
    for end in range(len(block), 0, -1):
        for subblock_len in range(1, end // 2 + 1):
            if end % subblock_len != 0:
                continue
            subblocks = [block[i : i + subblock_len] for i in range(0, end, subblock_len)]
            yield ((end // subblock_len) * subblock_len, subblocks)


def to_node(val, avar=None) -> nodes.NodeNG:
    assert not isinstance(val, list)
    if isinstance(val, nodes.NodeNG):
        return val
    if avar is not None and isinstance(avar.parent, nodes.Name):
        return nodes.Name(val)
    return nodes.Const(val)