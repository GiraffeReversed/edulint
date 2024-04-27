from typing import Generator, Optional, Callable, List, Union
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
    def get_essors(block: CFGBlock, direction: "Direction") -> Generator[CFGBlock, None, None]:
        attr = direction.name.lower()
        for edge in getattr(block, attr):
            yield getattr(edge, "target" if direction == Direction.SUCCESSORS else "source")


def essors_from_locs(
    locs: List[CFGLoc],
    direction: Direction,
    stop_on: Optional[Callable[[CFGLoc], bool]],
    include_start: bool,
    include_end: bool,
    explore_functions: bool,
) -> Generator[CFGLoc, None, None]:
    def explore_function(node: nodes.FunctionDef) -> Generator[CFGLoc, None, None]:
        assert direction == Direction.SUCCESSORS
        yield from dfs_rec(node.args.cfg_loc.block, 0)

    def try_explore_function(loc: CFGLoc) -> Generator[CFGLoc, None, None]:
        if explore_functions and isinstance(loc.node, nodes.FunctionDef):
            yield from explore_function(loc.node)

    def dfs_rec(current_block: CFGBlock, from_pos: int = 0) -> Generator[CFGLoc, None, None]:
        for nth in range(from_pos, len(current_block.locs)):
            i = Direction.to_index(nth, direction)
            current_loc = current_block.locs[i]

            if current_loc in visited:
                return
            visited.add(current_loc)

            stop = stop_on(current_loc)
            if not stop or include_end:
                yield current_loc
                yield from try_explore_function(current_loc)
            if stop:
                return

        for essor in Direction.get_essors(current_block, direction):
            i = Direction.to_index(0, direction)
            if len(essor.locs) == 0 or essor.locs[i] in visited:
                continue

            yield from dfs_rec(essor)

    stop_on = stop_on if stop_on is not None else lambda _v: False
    visited = set()
    for loc in locs:
        # to unwrap nodes that are not part of the CFG (for, if, while, ...)
        loc = loc.block.locs[loc.pos]
        if loc in visited:
            continue
        visited.add(loc)

        if include_start:
            stop = stop_on(loc)
            yield loc
            if stop:
                continue

        yield from try_explore_function(loc)

        yield from dfs_rec(loc.block, loc.pos + 1)


def successors_from_loc(
    loc: CFGLoc,
    stop_on: Optional[Callable[[CFGLoc], bool]] = None,
    include_start: bool = False,
    include_end: bool = False,
    explore_functions: bool = False,
) -> Generator[CFGLoc, None, None]:
    yield from essors_from_locs(
        [loc], Direction.SUCCESSORS, stop_on, include_start, include_end, explore_functions
    )


def successors_from_locs(
    locs: List[CFGLoc],
    stop_on: Optional[Callable[[CFGLoc], bool]] = None,
    include_start: bool = False,
    include_end: bool = False,
    explore_functions: bool = False,
) -> Generator[CFGLoc, None, None]:
    yield from essors_from_locs(
        locs, Direction.SUCCESSORS, stop_on, include_start, include_end, explore_functions
    )


def predecessors_from_loc(
    loc: CFGLoc,
    stop_on: Optional[Callable[[CFGLoc], bool]] = None,
    include_start: bool = False,
    include_end: bool = False,
    explore_functions: bool = False,
) -> Generator[CFGLoc, None, None]:
    yield from essors_from_locs(
        [loc], Direction.PREDECESSORS, stop_on, include_start, include_end, explore_functions
    )


def get_cfg_loc(in_stmt: nodes.NodeNG) -> CFGLoc:
    while not hasattr(in_stmt, "cfg_loc"):
        in_stmt = in_stmt.parent
        assert in_stmt is not None

    return in_stmt.cfg_loc


def syntactic_children_locs_from(
    loc: CFGLoc,
    syntactic: nodes.NodeNG,
) -> Generator[CFGLoc, None, None]:
    if isinstance(syntactic, list):
        stop_on = lambda loc: all(  # noqa: E731
            s not in loc.node.node_ancestors() for s in syntactic
        )
    else:
        stop_on = lambda loc: syntactic not in loc.node.node_ancestors()  # noqa: E731

    for succ in successors_from_loc(
        loc,
        stop_on=stop_on,
        include_start=True,
        include_end=False,
    ):
        yield succ


def get_first_locs_after(loc):
    if isinstance(loc, list):
        stop_on = lambda succ: all(  # noqa: E731
            s.node not in succ.node.node_ancestors() for s in loc
        )
    else:
        stop_on = lambda succ: loc.node not in succ.node.node_ancestors()  # noqa: E731

    for succ in (successors_from_locs if isinstance(loc, list) else successors_from_loc)(
        loc,
        stop_on=stop_on,
        include_start=False,
        include_end=True,
    ):
        if stop_on(succ):
            yield succ
