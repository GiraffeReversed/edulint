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

    if isinstance(loc.node, nodes.Arguments):
        return None, None

    if isinstance(parent, nodes.With):
        if loc.node == parent.items[0][0]:
            return None, parent.cfg_loc
        if any(loc.node == v for item in parent.items for v in item):
            return None, None
        return loc, None

    if (isinstance(parent, (nodes.If, nodes.While)) and loc.node == parent.test) or (
        isinstance(parent, nodes.For) and loc.node in (parent.target, parent.iter)
    ):
        return None, parent.cfg_loc

    if isinstance(parent, (nodes.TryExcept, nodes.ExceptHandler)) and loc.node == parent.body[0]:
        return loc, parent.cfg_loc

    return loc, None


def syntactic_children_locs_from_old(
    loc: CFGLoc,
    syntactic: nodes.NodeNG,
) -> Generator[CFGLoc, None, None]:
    if isinstance(syntactic, list):
        # stop_on = lambda loc: all(  # noqa: E731
        #     s != loc.node and s not in loc.node.node_ancestors() for s in syntactic
        # )
        syntactic_set = set(syntactic)

        def stop_on(loc):
            return len(syntactic_set & (set(loc.node.node_ancestors()) | {loc.node})) == 0

    else:
        stop_on = (  # noqa: E731
            lambda loc: syntactic != loc.node and syntactic not in loc.node.node_ancestors()
        )

    for succ in successors_from_loc(
        loc,
        stop_on_loc=stop_on,
        include_start=True,
        include_end=False,
    ):
        yield succ


def syntactic_children_locs_from(
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


def get_first_locs_after(locs: List[CFGLoc]):
    if isinstance(locs, list):
        loc_node_set = set(s.node for s in locs)
    else:
        locs = [locs]
        loc_node_set = {locs.node}

    def stop_on(block, from_pos, to_pos):
        # it is enough to check last; locs_after inside a loc's block
        # are handled separately
        last = block.locs[to_pos - 1].node
        return len(loc_node_set & (set(last.node_ancestors()) | {last})) == 0

    block_locs = defaultdict(list)
    for loc in sorted(locs, key=lambda loc: loc.pos):
        block_locs[loc.block].append(loc)

    for block, same_block_locs in list(block_locs.items()):
        for i in range(len(same_block_locs) - 1):
            lt = same_block_locs[i]
            rt = same_block_locs[i + 1]

            if lt.pos + 1 != rt.pos:
                yield block.locs[lt.pos + 1]
                block_locs.pop(block)
                break

    for succ_block, from_pos, to_pos in essor_blocks_from_locs(
        [same_block_locs[-1] for same_block_locs in block_locs.values()],
        Direction.SUCCESSORS,
        stop_on_block=stop_on,
        stop_on_loc=None,
        include_start=False,
        include_end=True,
    ):
        if stop_on(succ_block, from_pos, to_pos):
            same_block_poses = [loc.pos for loc in locs if loc.block == succ_block]
            yield succ_block.locs[max(same_block_poses, default=-1) + 1]
