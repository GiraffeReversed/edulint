# adapted from https://github.com/pyta-uoft/pyta/blob/4c858623549e24a49fea7aef9c8ec7c20c836bd6/python_ta/cfg/graph.py

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Generator, List, Optional, Set

from astroid import nodes

from edulint.linting.analyses.var_events import VarEvents


class ControlFlowGraph:
    """A graph representing the control flow of a Python program."""

    start: CFGBlock
    end: CFGBlock
    # The unique id of this cfg. Defaults to 0 if not initialized in a CFGVisitor instance.
    cfg_id: int
    # block_count is used as an "autoincrement" to ensure the block ids are unique.
    block_count: int
    # blocks (with at least one statement) that will never be executed in runtime.
    unreachable_blocks: Set[CFGBlock]

    def __init__(self, cfg_id: int = 0) -> None:
        self.block_count = 0
        self.cfg_id = cfg_id
        self.unreachable_blocks = set()
        self.start = self.create_block()
        self.end = self.create_block()

    def create_block(
        self, pred: Optional[CFGBlock] = None, edge_label: Optional[Any] = None
    ) -> CFGBlock:
        """Create a new CFGBlock for this graph.

        If pred is specified, set that block as a predecessor of the new block.

        If edge_label is specified, set the corresponding edge in the CFG with that label.
        """
        new_block = CFGBlock(self.block_count)
        self.unreachable_blocks.add(new_block)

        self.block_count += 1
        if pred:
            self.link_or_merge(pred, new_block, edge_label)
        return new_block

    def link(self, source: CFGBlock, target: CFGBlock) -> None:
        """Link source to target."""
        if not source.is_jump():
            CFGEdge(source, target)

    def link_or_merge(
        self, source: CFGBlock, target: CFGBlock, edge_label: Optional[Any] = None
    ) -> None:
        """Link source to target, or merge source into target if source is empty.

        An "empty" node for this purpose is when source has no statements.

        source with a jump statement cannot be further linked or merged to
        another target.

        If edge_label is specified, set the corresponding edge in the CFG with that label.
        """
        if source.is_jump():
            return
        if source.locs == []:
            if source is self.start:
                self.start = target
            else:
                for edge in source.predecessors:
                    edge.target = target
                    target.predecessors.append(edge)
            # source is a utility block that helps build the cfg that does not
            # represent any part of the program so it is redundant.
            self.unreachable_blocks.remove(source)
        else:
            CFGEdge(source, target, edge_label)

    def multiple_link_or_merge(self, source: CFGBlock, targets: List[CFGBlock]) -> None:
        """Link source to multiple target, or merge source into targets if source is empty.

        An "empty" node for this purpose is when source has no statements.

        source with a jump statement cannot be further linked or merged to
        another target.

        Precondition:
            - source != cfg.start
        """
        if source.locs == []:
            for edge in source.predecessors:
                for t in targets:
                    CFGEdge(edge.source, t)
                edge.source.successors.remove(edge)
            source.predecessors = []
            self.unreachable_blocks.remove(source)
        else:
            for target in targets:
                self.link(source, target)

    def get_blocks(self) -> Generator[CFGBlock, None, None]:
        """Generate a sequence of all blocks in this graph."""
        stack = [(0, self.start)]
        visited = {self.start}

        while stack:
            i, block = stack.pop()
            if i == 0:
                yield block
            if i >= len(block.successors):
                continue

            stack.append((i + 1, block))

            next_block = block.successors[i].target
            if next_block in visited:
                continue

            stack.append((0, next_block))
            visited.add(next_block)

    def get_blocks_postorder(self) -> Generator[CFGBlock, None, None]:
        """Return the sequence of all blocks in this graph in the order of
        a post-order traversal."""
        yield from self._get_blocks_postorder(self.start, set())

    def _get_blocks_postorder(self, block: CFGBlock, visited) -> Generator[CFGBlock, None, None]:
        if block.id in visited:
            return

        visited.add(block.id)
        for succ in block.successors:
            yield from self._get_blocks_postorder(succ.target, visited)

        yield block

    def get_edges(self) -> Generator[CFGEdge, None, None]:
        """Generate a sequence of all edges in this graph."""
        yield from self._get_edges(self.start, set())

    def _get_edges(self, block: CFGBlock, visited: Set[int]) -> Generator[CFGEdge, None, None]:
        if block.id in visited:
            return

        visited.add(block.id)

        for edge in block.successors:
            yield edge
            yield from self._get_edges(edge.target, visited)

    def update_block_reachability(self) -> None:
        for block in self.get_blocks():
            block.reachable = True
            if block in self.unreachable_blocks:
                self.unreachable_blocks.remove(block)


@dataclass
class CFGLoc:
    block: CFGBlock
    pos: int
    node: nodes.NodeNG
    var_events: VarEvents = field(default_factory=VarEvents)

    def __eq__(self, other):
        return self.block == other.block and self.pos == other.pos and self.node == other.node

    def __hash__(self):
        return hash((self.block, self.pos, self.node))

    def __repr__(self):
        return f"CFGLoc(node={self.node!r})"


class CFGBlock:
    """A node in a control flow graph.

    Represents a maximal block of code whose statements are guaranteed to execute in sequence.
    """

    # A unique identifier
    id: int
    # The statements in this block.
    locs: List[CFGLoc]
    # This block's in-edges (from blocks that can execute immediately before this one).
    predecessors: List[CFGEdge]
    # This block's out-edges (to blocks that can execute immediately after this one).
    successors: List[CFGEdge]
    # Whether there exists a path from the start block to this block.
    reachable: bool

    def __init__(self, id_: int) -> None:
        """Initialize a new CFGBlock."""
        self.id = id_
        self.locs = []
        self.predecessors = []
        self.successors = []
        self.reachable = False

    def __repr__(self):
        return f"CFGBlock(len={len(self.locs)}, fst={self.locs[0].node!r})"

    def add_statement(self, statement: nodes.NodeNG) -> None:
        if not self.is_jump():
            loc = CFGLoc(self, len(self.locs), statement)
            self.locs.append(loc)
            statement.cfg_loc = loc

    def _CF_statement_to_pos(self, statement: nodes.NodeNG) -> int:
        if isinstance(statement, nodes.Module):
            pos = 0
            # assert self.locs[pos] == self.locs[self._CF_statement_to_pos(statement.body[0])]
        elif isinstance(statement, nodes.If):
            pos = len(self.locs) - 1
            assert self.locs[pos].node == statement.test
        elif isinstance(statement, nodes.While):
            pos = 0
            assert self.locs[pos].node == statement.test
        elif isinstance(statement, nodes.For):
            pos = len(self.locs) - 1
            assert self.locs[pos].node == statement.iter
        elif isinstance(statement, (nodes.Try, nodes.TryStar)):
            pos = 0
            statement_loc = statement.body[0].cfg_loc
            assert self.locs[pos].node == statement_loc.block.locs[statement_loc.pos].node
        elif isinstance(statement, nodes.ExceptHandler):
            pos = 0
            first_body_loc = statement.body[0].cfg_loc
            first_body_node = first_body_loc.block.locs[first_body_loc.pos].node
            assert self.locs[pos].node in (statement.name, first_body_node)
        elif isinstance(statement, nodes.With):
            pos = len(self.locs)
        else:
            assert False, f"unreachable, but {type(statement)}"
        return pos

    def add_CF_statement(self, statement: nodes.NodeNG) -> None:
        pos = self._CF_statement_to_pos(statement)
        loc = CFGLoc(self, pos, statement)
        statement.cfg_loc = loc

    @property
    def jump(self) -> Optional[nodes.NodeNG]:
        if len(self.locs) > 0:
            return self.locs[-1]

    def is_jump(self) -> bool:
        """Returns True if the block has a statement that branches
        the control flow (ex: `break`)"""
        return isinstance(self.jump, (nodes.Break, nodes.Continue, nodes.Return, nodes.Raise))


class CFGEdge:
    """An edge in a control flow graph.

    Edges are directed, and in the future may be augmented with auxiliary metadata about the control flow.
    """

    source: CFGBlock
    target: CFGBlock
    label: Optional[Any]

    def __init__(
        self, source: CFGBlock, target: CFGBlock, edge_label: Optional[Any] = None
    ) -> None:
        self.source = source
        self.target = target
        self.label = edge_label
        self.source.successors.append(self)
        self.target.predecessors.append(self)
