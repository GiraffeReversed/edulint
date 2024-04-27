from typing import Generator, List
from enum import Enum

from astroid import nodes

from edulint.linting.analyses.cfg.graph import CFGBlock


class Direction(Enum):
    SUCCESSORS = 1
    PREDECESSORS = -1

    @staticmethod
    def to_index(pos: int, direction: "Direction") -> int:
        if direction == Direction.SUCCESSORS:
            return pos
        elif direction == Direction.PREDECESSORS:
            return -pos - 1
        assert False, "unreachable"

    @staticmethod
    def get_essors(block: CFGBlock, direction: "Direction") -> Generator[CFGBlock, None, None]:
        attr = direction.name.lower()
        for edge in getattr(block, attr):
            yield getattr(edge, "target" if direction == Direction.SUCCESSORS else "source")


def essors_from_statement(
    stmt: nodes.NodeNG, direction: Direction, include_start: bool
) -> Generator[nodes.NodeNG, None, None]:
    def get_start_position(stmt: nodes.NodeNG, statements: List[nodes.NodeNG]):
        for pos in range(len(statements)):
            if statements[Direction.to_index(pos, direction)] == stmt:
                return pos
        assert False, "unreachable"

    def dfs_rec(current_block: CFGBlock, from_pos: int = 0) -> Generator[nodes.NodeNG, None, None]:
        for nth in range(from_pos, len(current_block.statements)):
            i = Direction.to_index(nth, direction)
            current_stmt = current_block.statements[i]
            yield current_stmt

        for essor in Direction.get_essors(current_block, direction):
            if essor in visited:
                continue

            visited.add(essor)
            yield from dfs_rec(essor)

    if include_start:
        yield stmt

    current_block = stmt.cfg_block
    stmt_pos = get_start_position(stmt, current_block.statements)

    visited = set()
    yield from dfs_rec(current_block, stmt_pos + 1)


def successors_from_statement(
    stmt: nodes.NodeNG, include_start: bool = False
) -> Generator[nodes.NodeNG, None, None]:
    yield from essors_from_statement(stmt, Direction.SUCCESSORS, include_start)


def predecessors_from_statement(
    stmt: nodes.NodeNG, include_start: bool = False
) -> Generator[nodes.NodeNG, None, None]:
    yield from essors_from_statement(stmt, Direction.PREDECESSORS, include_start)


def get_stmt_ref(in_stmt: nodes.NodeNG):
    while not hasattr(in_stmt, "cfg_block"):
        in_stmt = in_stmt.parent
        assert in_stmt is not None

    block = in_stmt.cfg_block
    for i, stmt in enumerate(block.statements):
        if stmt == in_stmt:
            return block, i
    assert False, "unreachable"
