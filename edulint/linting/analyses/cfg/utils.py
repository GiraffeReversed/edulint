from typing import Generator, Optional, Callable, List, Tuple, Iterator, Union
from collections import defaultdict
from enum import Enum

from astroid import nodes

from edulint.linting.analyses.cfg.graph import CFGBlock, CFGLoc


def unwrap(loc: CFGLoc) -> CFGLoc:
    """unwraps nodes that are not part of the CFG (for, if, while, ...)"""
    return loc.block.locs[loc.pos]


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

    def triage_block(
        current_block: CFGBlock, from_pos: int, to_pos: int, is_first: bool
    ) -> Tuple[bool, bool, Tuple[int, int]]:
        stop_on_current_block = stop_on_block is not None and stop_on_block(
            current_block, from_pos, to_pos
        )
        if (
            stop_on_current_block
            and not include_end
            and (not include_start or not is_first)
            and stop_on_loc is None
        ):
            return True, False, (None, None)

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
                            to_pos = i + 1
                        else:
                            from_pos = i
                    else:
                        if direction == Direction.SUCCESSORS:
                            to_pos = i
                        else:
                            from_pos = i + 1
                    return True, True, (from_pos, to_pos)

        return stop_on_current_block, True, (from_pos, to_pos)

    def dfs_iter(current_block: CFGBlock, from_pos: int, to_pos: int, is_first: bool):
        stack = [(current_block, from_pos, to_pos, is_first, 0)]

        while stack:
            current_block, from_pos, to_pos, is_first, essor_i = stack.pop()

            if essor_i == 0:
                should_stop, should_yield, (from_pos, to_pos) = triage_block(
                    current_block, from_pos, to_pos, is_first
                )
                if should_yield and from_pos != to_pos:
                    yield current_block, from_pos, to_pos
                if should_stop:
                    continue

            if (direction == Direction.SUCCESSORS and essor_i >= len(current_block.successors)) or (
                direction == Direction.PREDECESSORS and essor_i >= len(current_block.predecessors)
            ):
                continue
            stack.append((current_block, from_pos, to_pos, is_first, essor_i + 1))

            if (direction == Direction.SUCCESSORS and to_pos == len(current_block.locs)) or (
                direction == Direction.PREDECESSORS and from_pos == 0
            ):
                essor = list(Direction.get_essors(current_block, direction))[essor_i]
                if len(essor.locs) == 0:
                    continue

                elif essor not in visited:
                    visited[essor] = 0, len(essor.locs)
                    stack.append((essor, 0, len(essor.locs), False, 0))

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
                    stack.append((essor, new_from_pos, new_to_pos, False, 0))

    visited = {}
    for loc in locs:
        loc = unwrap(loc)
        vblock = visited.get(loc.block)

        if vblock is None:
            if direction == Direction.SUCCESSORS:
                from_pos = loc.pos if include_start else loc.pos + 1
                to_pos = len(loc.block.locs)
            else:
                from_pos = 0
                to_pos = loc.pos + 1 if include_start else loc.pos

            visited[loc.block] = from_pos, to_pos
            yield from dfs_iter(loc.block, from_pos, to_pos, is_first=True)
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

            yield from dfs_iter(loc.block, from_pos, to_pos, is_first=True)


def successor_blocks_from_locs(
    locs: List[CFGLoc],
    stop_on_loc: Optional[Callable[[CFGLoc], bool]] = None,
    stop_on_block: Optional[Callable[[CFGBlock, int, int], bool]] = None,
    include_start: bool = False,
    include_end: bool = False,
) -> Iterator[Tuple[CFGBlock, int, int]]:
    """
    Iterates blocks reachable from given locs (DFS).

    Args:
        locs: CFG locations to start from
        stop_on_loc: condition to test on a location to determine if the iteration should stop here
        stop_on_block: condition to test on a block to determine if the iteration should stop here
        include_start: whether to include the initial locations in locs argument
        include_end: whether to include the node on which the iteration is stopped

    Yields:
        a triplet of block and two indexes into its locs; the indexes determine which part of the block would be
        iterated over when iterating over locations (for cases when iteration starts in the middle of a block)
    """
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
    """
    Iterates blocks from which given locs are reachable (reversed DFS).

    Args:
        locs: CFG locations to start from
        stop_on_loc: condition to test on a location to determine if the iteration should stop here
        stop_on_block: condition to test on a block to determine if the iteration should stop here
        include_start: whether to include the initial locations in locs argument
        include_end: whether to include the node on which the iteration is stopped

    Yields:
        a triplet of block and two indexes into its locs; the indexes determine which part of the block would be
        iterated over when iterating over locations (for cases when iteration starts in the middle of a block)
    """
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
) -> Iterator[CFGLoc]:
    """
    Iterates locs reachable from the given loc (DFS).

    Args:
        loc: the CFG location to start from
        stop_on_loc: condition to test on a location to determine if the iteration should stop here
        stop_on_block: condition to test on a block to determine if the iteration should stop here
        include_start: whether to include the initial locations in locs argument
        include_end: whether to include the node on which the iteration is stopped
        explore_functions: whether the iteration should continue into function definitions in the place
          where they are defined
        explore_classes: whether the iteration should continue into class definitions in the place where
          they are defined

    Yields:
        reachable locations
    """
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
) -> Iterator[CFGLoc]:
    """
    Iterates locs reachable from given locs (DFS).

    Args:
        loc: CFG locations to start from
        stop_on_loc: condition to test on a location to determine if the iteration should stop here
        stop_on_block: condition to test on a block to determine if the iteration should stop here
        include_start: whether to include the initial locations in locs argument
        include_end: whether to include the node on which the iteration is stopped
        explore_functions: whether the iteration should continue into function definitions in the place
          where they are defined
        explore_classes: whether the iteration should continue into class definitions in the place where
          they are defined

    Yields:
        reachable locations
    """
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
) -> Iterator[CFGLoc]:
    """
    Iterates locs from which given loc is reachable (reversed DFS).

    Args:
        loc: CFG locations to start from
        stop_on_loc: condition to test on a location to determine if the iteration should stop here
        stop_on_block: condition to test on a block to determine if the iteration should stop here
        include_start: whether to include the initial locations in locs argument
        include_end: whether to include the node on which the iteration is stopped
        explore_functions: whether the iteration should continue into function definitions in the place
          where they are defined
        explore_classes: whether the iteration should continue into class definitions in the place where
          they are defined

    Yields:
        reachable locations
    """
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
    """Returns the CFGLoc of this node or its closest parent."""
    while not hasattr(in_stmt, "cfg_loc"):
        in_stmt = in_stmt.parent
        assert in_stmt is not None

    return in_stmt.cfg_loc


def get_stmt_locs(loc: CFGLoc) -> Tuple[Optional[CFGLoc], Optional[CFGLoc]]:
    """
    Takes a location and returns a tuple with possible statement locations
    (locations which are not a true part of the CFG = if statements, not just
    their conditions, etc.)
    """
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

    if isinstance(parent, nodes.Try) and loc.node == parent.body[0]:
        return loc, parent.cfg_loc

    return loc, None


def syntactic_children_locs(
    syntactic: Union[nodes.NodeNG, List[nodes.NodeNG]],
    include_stmt_locs: bool = False,
    explore_functions: bool = False,
    explore_classes: bool = False,
) -> Iterator[CFGLoc]:
    """
    Returns all locations that are syntactic descendants of a node, not just its
    children.

    Args:
        syntactic: the node or nodes to start from
        include_stmt_locations: whether statement locations should be included, see get_stmt_locs
        explore_functions: whether nested function definitions should also be iterated
        explore_classes: whether nested class definitions shoudl also be iterated
    """
    if isinstance(syntactic, nodes.NodeNG):
        node = syntactic
    else:
        node = syntactic[0]

    assert hasattr(node, "cfg_loc")

    yield from syntactic_children_locs_from(
        node.cfg_loc, syntactic, include_stmt_locs, explore_functions, explore_classes
    )


def syntactic_children_locs_from(
    loc: CFGLoc,
    syntactic: Union[nodes.NodeNG, List[nodes.NodeNG]],
    include_stmt_locs: bool = False,
    explore_functions: bool = False,
    explore_classes: bool = False,
) -> Iterator[CFGLoc]:
    """
    Returns all locations that are syntactic descendants of a node, not just its
    children, starting from a location.

    Args:
        loc: the location to start from
        syntactic: the node or nodes to start from
        include_stmt_locations: whether statement locations should be included, see get_stmt_locs
        explore_functions: whether nested function definitions should also be iterated
        explore_classes: whether nested class definitions shoudl also be iterated
    """
    if isinstance(loc, CFGLoc):
        loc = [loc]
    if isinstance(syntactic, nodes.NodeNG):
        syntactic = [syntactic]

    syntactic = [n.cfg_loc for n in syntactic]

    for is_in, block, from_pos, to_pos in get_locs_in_and_after_from(loc, syntactic):
        if is_in:
            for i in range(from_pos, to_pos):
                loc = block.locs[i]
                if not include_stmt_locs:
                    locs = [loc]
                else:
                    locs = [stmt_loc for stmt_loc in get_stmt_locs(loc) if stmt_loc is not None]

                for loc in locs:
                    yield loc

                    if isinstance(loc.node, nodes.FunctionDef) and explore_functions:
                        functions = [loc.node]
                    elif isinstance(loc.node, nodes.ClassDef) and explore_classes:
                        functions = [n for n in loc.node.body if isinstance(n, nodes.FunctionDef)]
                    else:
                        functions = []

                    for function in functions:
                        yield from successors_from_loc(
                            function.args.cfg_loc,
                            include_start=True,
                            explore_functions=explore_functions,
                            explore_classes=explore_classes,
                        )


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
        unwrapped = unwrap(loc)
        if unwrapped == loc:
            block_locs[loc.block].append(loc)
            continue

        for i in range(unwrapped.pos, len(unwrapped.block.locs)):
            subloc = unwrapped.block.locs[i]
            assert subloc.node != loc.node
            if loc.node in subloc.node.node_ancestors():
                block_locs[loc.block].append(subloc)
            else:
                break

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
