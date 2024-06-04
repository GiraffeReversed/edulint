from typing import Generator, Optional, Callable, List, Tuple, Iterator
from collections import defaultdict
from enum import Enum

from astroid import nodes

from edulint.linting.analyses.cfg.graph import CFGBlock, CFGLoc


class Direction(Enum):
    SUCCESSORS = 1
    PREDECESSORS = -1

    @staticmethod
    def to_index(pos: int, direction: "Direction") -> int:
        if direction == Direction.SUCCESSORS:
            return pos
        if direction == Direction.PREDECESSORS:
            return -pos - 1
        assert False, "unreachable"

    @staticmethod
    def to_range(i: int, block_len: int, direction: "Direction") -> Iterator[int]:
        if direction == Direction.SUCCESSORS:
            return range(i, block_len)
        if direction == Direction.PREDECESSORS:
            return range(i, -1, -1)
        assert False, "unreachable"

    @staticmethod
    def get_essors(block: CFGBlock, direction: "Direction") -> Generator[CFGBlock, None, None]:
        attr = direction.name.lower()
        for edge in getattr(block, attr):
            yield getattr(edge, "target" if direction == Direction.SUCCESSORS else "source")


def essor_blocks_from_locs(
    locs: List[CFGLoc],
    direction: Direction,
    stop_on_loc: Optional[Callable[[CFGLoc], bool]],
    stop_on_block: Optional[Callable[[CFGBlock, int, int], bool]],
    include_start: bool,
    include_end: bool,
) -> Iterator[Tuple[CFGBlock, int, int]]:
    def dfs_rec(current_block: CFGBlock, from_pos: int, to_pos: int, is_first: bool):

        stop_on_current_block = stop_on_block is not None and stop_on_block(
            current_block, from_pos, to_pos
        )
        if (
            stop_on_current_block
            and not include_end
            and (not include_start or not is_first)
            and stop_on_loc is None
        ):
            return

        if (stop_on_block is None or stop_on_current_block) and stop_on_loc is not None:
            if direction == Direction.SUCCESSORS:
                rng = range(from_pos, to_pos)
            else:
                rng = range(to_pos - 1, from_pos - 1, -1)

            for i in rng:
                current_loc = current_block.locs[i]
                if stop_on_loc is not None and stop_on_loc(current_loc):
                    if include_end:
                        if direction == Direction.SUCCESSORS:
                            yield current_block, from_pos, i + 1
                        else:
                            yield current_block, i, to_pos
                    else:
                        if direction == Direction.SUCCESSORS:
                            yield current_block, from_pos, i
                        else:
                            yield current_block, i + 1, to_pos
                    return

        # stop_on_loc is None or no stop in this block
        if from_pos != to_pos:
            yield current_block, from_pos, to_pos

        if stop_on_current_block:
            return

        if (direction == Direction.SUCCESSORS and to_pos == len(current_block.locs)) or (
            direction == Direction.PREDECESSORS and from_pos == 0
        ):
            for essor in Direction.get_essors(current_block, direction):
                if len(essor.locs) == 0:
                    continue

                elif essor not in visited:
                    visited[essor] = 0, len(essor.locs)
                    yield from dfs_rec(essor, 0, len(essor.locs), is_first=False)

                else:
                    vfrom, vto = visited[essor]
                    if vfrom == 0 and vto == len(essor.locs):
                        continue

                    if direction == Direction.SUCCESSORS:
                        assert vto == len(essor.locs)
                        new_from_pos = 0
                        new_to_pos = vfrom
                    else:
                        assert vfrom == 0
                        new_from_pos = vto
                        new_to_pos = len(essor.locs)

                    visited[essor] = 0, len(essor.locs)
                    yield from dfs_rec(essor, new_from_pos, new_to_pos, is_first=False)

    visited = {}
    for loc in locs:
        # to unwrap nodes that are not part of the CFG (for, if, while, ...)
        loc = loc.block.locs[loc.pos]
        vblock = visited.get(loc.block)

        if vblock is None:
            if direction == Direction.SUCCESSORS:
                from_pos = loc.pos if include_start else loc.pos + 1
                to_pos = len(loc.block.locs)
            else:
                from_pos = 0
                to_pos = loc.pos + 1 if include_start else loc.pos

            visited[loc.block] = from_pos, to_pos
            yield from dfs_rec(loc.block, from_pos, to_pos, is_first=True)
        else:
            vfrom, vto = vblock
            if vfrom <= loc.pos < vto:
                continue

            if direction == Direction.SUCCESSORS:
                assert vto == len(loc.block.locs)
                from_pos = loc.pos if include_start else loc.pos + 1
                to_pos = vfrom
                visited[loc.block] = from_pos, vto
            else:
                assert vfrom == 0
                from_pos = vto
                to_pos = loc.pos + 1 if include_start else loc.pos
                visited[loc.block] = vfrom, to_pos

            yield from dfs_rec(loc.block, from_pos, to_pos, is_first=True)


def successor_blocks_from_locs(
    locs: List[CFGLoc],
    stop_on_loc: Optional[Callable[[CFGLoc], bool]] = None,
    stop_on_block: Optional[Callable[[CFGBlock, int, int], bool]] = None,
    include_start: bool = False,
    include_end: bool = False,
):
    return essor_blocks_from_locs(
        locs, Direction.SUCCESSORS, stop_on_loc, stop_on_block, include_start, include_end
    )


def predecessor_blocks_from_locs(
    locs: List[CFGLoc],
    stop_on_loc: Optional[Callable[[CFGLoc], bool]] = None,
    stop_on_block: Optional[Callable[[CFGBlock, int, int], bool]] = None,
    include_start: bool = False,
    include_end: bool = False,
):
    return essor_blocks_from_locs(
        locs, Direction.PREDECESSORS, stop_on_loc, stop_on_block, include_start, include_end
    )


def essor_locs_from_locs(
    locs: List[CFGLoc],
    direction: Direction,
    stop_on_loc: Optional[Callable[[CFGLoc], bool]],
    stop_on_block: Optional[Callable[[CFGBlock], bool]],
    include_start: bool,
    include_end: bool,
    explore_functions: bool,
    explore_classes: bool,
):
    def explore_function(node: nodes.FunctionDef):
        assert direction == Direction.SUCCESSORS
        yield from essor_locs_from_locs(
            [node.args.cfg_loc],
            direction,
            stop_on_loc,
            stop_on_block,
            include_start,
            include_end,
            explore_functions,
            explore_classes,
        )

    def try_explore_function(loc: CFGLoc):
        if explore_functions and isinstance(loc.node, nodes.FunctionDef):
            yield from explore_function(loc.node)

    def explore_class(node: nodes.ClassDef):
        assert direction == Direction.SUCCESSORS
        for child in node.body:
            yield from try_explore_function(child.cfg_loc)

    def try_explore_class(loc: CFGLoc):
        if explore_classes and isinstance(loc.node, nodes.ClassDef):
            yield from explore_class(loc.node)

    for block, from_pos, to_pos in essor_blocks_from_locs(
        locs, direction, stop_on_loc, stop_on_block, include_start, include_end
    ):
        if direction == Direction.SUCCESSORS:
            rng = range(from_pos, to_pos)
        else:
            rng = range(to_pos - 1, from_pos - 1, -1)
        for i in rng:
            yield block.locs[i]
            yield from try_explore_function(block.locs[i])
            yield from try_explore_class(block.locs[i])


def successors_from_loc(
    loc: CFGLoc,
    stop_on_loc: Optional[Callable[[CFGLoc], bool]] = None,
    stop_on_block: Optional[Callable[[CFGBlock], bool]] = None,
    include_start: bool = False,
    include_end: bool = False,
    explore_functions: bool = False,
    explore_classes: bool = False,
) -> Generator[CFGLoc, None, None]:
    yield from essor_locs_from_locs(
        [loc],
        Direction.SUCCESSORS,
        stop_on_loc,
        stop_on_block,
        include_start,
        include_end,
        explore_functions,
        explore_classes,
    )


def successors_from_locs(
    locs: List[CFGLoc],
    stop_on_loc: Optional[Callable[[CFGLoc], bool]] = None,
    stop_on_block: Optional[Callable[[CFGBlock], bool]] = None,
    include_start: bool = False,
    include_end: bool = False,
    explore_functions: bool = False,
    explore_classes: bool = False,
) -> Generator[CFGLoc, None, None]:
    yield from essor_locs_from_locs(
        locs,
        Direction.SUCCESSORS,
        stop_on_loc,
        stop_on_block,
        include_start,
        include_end,
        explore_functions,
        explore_classes,
    )


def predecessors_from_loc(
    loc: CFGLoc,
    stop_on_loc: Optional[Callable[[CFGLoc], bool]] = None,
    stop_on_block: Optional[Callable[[CFGBlock], bool]] = None,
    include_start: bool = False,
    include_end: bool = False,
    explore_functions: bool = False,
    explore_classes: bool = False,
) -> Generator[CFGLoc, None, None]:
    yield from essor_locs_from_locs(
        [loc],
        Direction.PREDECESSORS,
        stop_on_loc,
        stop_on_block,
        include_start,
        include_end,
        explore_functions,
        explore_classes,
    )


def get_cfg_loc(in_stmt: nodes.NodeNG) -> CFGLoc:
    while not hasattr(in_stmt, "cfg_loc"):
        in_stmt = in_stmt.parent
        assert in_stmt is not None

    return in_stmt.cfg_loc


def get_stmt_locs(loc: CFGLoc) -> Tuple[Optional[CFGLoc], Optional[CFGLoc]]:
    parent = loc.node.parent

    if isinstance(loc.node, nodes.Arguments) or (
        isinstance(parent, nodes.For) and loc.node == parent.target
    ):
        return None, None

    if isinstance(parent, nodes.With):
        if loc.node == parent.items[0][0]:
            return None, parent.cfg_loc
        if any(loc.node == v for item in parent.items for v in item):
            return None, None
        return loc, None

    if (isinstance(parent, (nodes.If, nodes.While)) and loc.node == parent.test) or (
        isinstance(parent, nodes.For) and loc.node == parent.iter
    ):
        return None, parent.cfg_loc

    if isinstance(parent, nodes.TryExcept) and loc.node == parent.body[0]:
        return loc, parent.cfg_loc

    return loc, None


def syntactic_children_locs_from_old(
    loc: CFGLoc,
    syntactic: nodes.NodeNG,
) -> Generator[CFGLoc, None, None]:
    if isinstance(syntactic, list):
        syntactic_set = set(syntactic)
    else:
        syntactic_set = {syntactic}

    def stop_on_block(block, from_pos, to_pos):
        # if last is not nested, then none exectued after will be nested
        last = block.locs[to_pos - 1].node
        return len(syntactic_set & (set(last.node_ancestors()) | {last})) == 0

    def stop_on_loc(loc):
        return len(syntactic_set & (set(loc.node.node_ancestors()) | {loc.node})) == 0

    for succ in successors_from_loc(
        loc,
        stop_on_block=stop_on_block,
        stop_on_loc=stop_on_loc,
        include_start=True,
        include_end=False,
    ):
        yield succ


def syntactic_children_locs_from(
    loc: CFGLoc,
    syntactic: nodes.NodeNG,
) -> Generator[CFGLoc, None, None]:

    if isinstance(loc, CFGLoc):
        loc = [loc]
    if isinstance(syntactic, nodes.NodeNG):
        syntactic = [syntactic]

    syntactic = [n.cfg_loc for n in syntactic]

    for is_in, block, from_pos, to_pos in get_locs_in_and_after_from(loc, syntactic):
        if is_in:
            for i in range(from_pos, to_pos):
                yield block.locs[i]


def get_first_locs_after(locs: List[CFGLoc]):
    for is_in, block, from_pos, to_pos in get_locs_in_and_after(locs):
        if not is_in:
            yield block.locs[from_pos]


def get_locs_in_and_after(locs: List[CFGLoc]) -> Iterator[Tuple[bool, CFGBlock, int, int]]:
    yield from get_locs_in_and_after_from(locs, locs)


def _get_conseq_partition(block_locs, block):
    same_block_locs = block_locs.get(block, [])

    conseqs = []
    conseq = []

    for loc in same_block_locs:
        if len(conseq) == 0 or conseq[-1].pos + 1 == loc.pos:
            conseq.append(loc)
        else:
            conseqs.append(conseq)
            conseq = [loc]

    if len(conseq) > 0:
        conseqs.append(conseq)

    return conseqs


def get_locs_in_and_after_from(
    froms: List[CFGLoc], locs: List[CFGLoc]
) -> Iterator[Tuple[bool, CFGBlock, int, int]]:
    loc_node_set = set(s.node for s in locs)

    def stop_on(block, from_pos, to_pos):
        # it is enough to check last; locs_after inside a loc's block
        # are handled separately
        last = block.locs[to_pos - 1].node
        return len(loc_node_set & (set(last.node_ancestors()) | {last})) == 0

    block_froms = defaultdict(list)
    for loc in sorted(froms, key=lambda loc: loc.pos):
        block_froms[loc.block].append(loc)

    block_locs = defaultdict(list)
    for loc in sorted(locs, key=lambda loc: loc.pos):
        block_locs[loc.block].append(loc)

    for succ_block, from_pos, to_pos in successor_blocks_from_locs(
        [same_block_locs[0] for same_block_locs in block_froms.values()],
        stop_on_block=stop_on,
        include_start=True,
        include_end=True,
    ):
        stop = stop_on(succ_block, from_pos, to_pos)
        conseqs = _get_conseq_partition(block_locs, succ_block)

        if len(conseqs) == 0 or (
            len(conseqs) == 1 and conseqs[0][-1].pos + 1 >= len(succ_block.locs)
        ):
            yield not stop, succ_block, from_pos, to_pos
            continue

        for i, conseq in enumerate(conseqs):
            yield True, succ_block, conseq[0].pos, conseq[-1].pos + 1

            if i < len(conseqs) - 1:
                next = conseqs[i + 1]
                yield False, succ_block, conseq[-1].pos + 1, next[0].pos
            if i == len(conseqs) - 1 and conseq[-1].pos + 1 < len(succ_block.locs):
                yield False, succ_block, conseq[-1].pos + 1, len(succ_block.locs)
