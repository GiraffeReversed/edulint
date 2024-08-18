from typing import TYPE_CHECKING, List, Tuple, Dict, Optional, Iterator, Set

from astroid import nodes  # type: ignore
from pylint.checkers import BaseChecker  # type: ignore

if TYPE_CHECKING:
    from pylint.lint import PyLinter  # type: ignore

from edulint.linting.analyses.antiunify import antiunify, cprint  # noqa: F401
from edulint.linting.analyses.cfg.utils import (
    get_stmt_locs,
    syntactic_children_locs,
    successors_from_loc,
)
from edulint.linting.checkers.utils import is_block_comment
from edulint.linting.checkers.duplication.duplicate_if import duplicate_in_if
from edulint.linting.checkers.duplication.duplicate_sequence import similar_to_loop
from edulint.linting.checkers.duplication.duplicate_block import similar_to_block
from edulint.linting.checkers.duplication.utils import (
    is_duplication_candidate,
    get_loop_repetitions,
)


### helpers


def candidate_fst(nodes: List[nodes.NodeNG]) -> Iterator[nodes.NodeNG]:
    yield from enumerate(nodes)


def candidate_snd(nodes: List[nodes.NodeNG], i: int) -> Iterator[Tuple[int, nodes.NodeNG]]:
    fst = nodes[i]
    j = i + 1

    while j < len(nodes) and fst.tolineno >= nodes[j].fromlineno:
        j += 1

    for j in range(j, len(nodes)):
        yield j, nodes[j]


def get_siblings(node: nodes.NodeNG) -> List[nodes.NodeNG]:
    siblings = []
    sibling = node
    while sibling is not None:
        if break_on_stmt(sibling):
            break
        if not skip_stmt(sibling):
            siblings.append(sibling)
        sibling = sibling.next_sibling()

    assert len(siblings) > 0
    return siblings


def get_memoized_siblings(
    siblings: Dict[nodes.NodeNG, List[nodes.NodeNG]], node: nodes.NodeNG
) -> List[nodes.NodeNG]:
    sibs = siblings.get(node)
    if sibs is not None:
        return sibs

    sibs = siblings.get(node.previous_sibling())
    if sibs is not None:
        sibs = sibs[1:]
        siblings[node] = sibs
        return sibs

    sibs = get_siblings(node)
    siblings[node] = sibs
    return sibs


def get_stmt_range(
    stmt_to_index: Dict[nodes.NodeNG, int], nodes: List[nodes.NodeNG]
) -> Optional[Tuple[int, int]]:
    last_i = stmt_to_index.get(nodes[-1])
    return stmt_to_index[nodes[0]], last_i + 1 if last_i is not None else None


def overlap(
    stmt_nodes: List[nodes.NodeNG], range1: Tuple[int, int], range2: Tuple[int, int]
) -> bool:
    first1, last1 = range1
    first2, last2 = range2
    if last1 is None or last2 is None:
        return True

    last_node = stmt_nodes[last1 - 1]
    first_node = stmt_nodes[first2]
    return last_node.tolineno >= first_node.fromlineno


def break_on_stmt(node: nodes.NodeNG) -> bool:
    return isinstance(node, (nodes.Assert, nodes.ClassDef))


def skip_stmt(node: nodes.NodeNG) -> bool:
    return (
        is_block_comment(node)
        or isinstance(node, nodes.Pass)
        or (isinstance(node, (nodes.Import, nodes.ImportFrom)) and node.parent == node.root())
        or (
            isinstance(node, (nodes.Assign, nodes.AugAssign, nodes.AnnAssign))
            and len(node.cfg_loc.uses) == 0
        )
    )


def include_in_stmts(node: nodes.NodeNG) -> bool:
    return not break_on_stmt(node) and not skip_stmt(node)


def get_statement_nodes(node: nodes.Module) -> List[nodes.NodeNG]:
    return sorted(
        (
            stmt_loc.node
            for loc in successors_from_loc(
                node.cfg_loc, include_start=True, explore_functions=True, explore_classes=True
            )
            for stmt_loc in get_stmt_locs(loc)
            if stmt_loc is not None and include_in_stmts(stmt_loc.node)
        ),
        key=lambda node: (
            node.fromlineno,
            node.col_offset if node.col_offset is not None else float("inf"),
        ),
    )


def get_duplicate_nodes(ns: List[nodes.NodeNG]) -> Set[nodes.NodeNG]:
    return {loc.node for loc in syntactic_children_locs(ns, include_stmt_locs=True)}


### control functions


def is_similar_to_loop(checker, siblings: List[nodes.NodeNG]) -> bool:
    if (
        (
            not checker.linter.is_message_enabled("similar-to-loop")
            and not checker.linter.is_message_enabled("similar-to-loop-merge")
        )
        or len(siblings) < 3
        or any(isinstance(node, nodes.FunctionDef) for node in siblings)
    ):
        return False

    for end, to_aunify in get_loop_repetitions(siblings):
        if not is_duplication_candidate(to_aunify):
            continue
        if similar_to_loop(checker, to_aunify):
            return True
    return False


def is_duplicate_in_if(checker, node: nodes.NodeNG) -> Tuple[bool, bool]:
    if not isinstance(node, nodes.If):
        return False, False
    return duplicate_in_if(checker, node)


def get_similar_to_block_candidates(
    checker,
    stmt_nodes: List[nodes.NodeNG],
    stmt_to_index: Dict[nodes.NodeNG, int],
    siblings: Dict[nodes.NodeNG, List[nodes.NodeNG]],
    i: int,
):
    if not checker.linter.is_message_enabled(
        "similar-to-function"
    ) and not checker.linter.is_message_enabled("similar-to-call"):
        return

    fst = stmt_nodes[i]
    fst_siblings = get_memoized_siblings(siblings, fst)

    for j, snd in candidate_snd(stmt_nodes, i):
        snd_siblings = get_memoized_siblings(siblings, snd)

        for length in range(min(len(fst_siblings), len(snd_siblings), j - i), 0, -1):
            if length == 1 and (
                isinstance(fst, (nodes.Assign, nodes.Expr))
                or isinstance(snd, (nodes.Assign, nodes.Expr))
            ):
                break

            to_aunify = [tuple(fst_siblings[:length]), tuple(snd_siblings[:length])]
            ranges = [
                get_stmt_range(stmt_to_index, to_aunify[0]),
                get_stmt_range(stmt_to_index, to_aunify[1]),
            ]

            if not overlap(stmt_nodes, ranges[0], ranges[1]) and is_duplication_candidate(
                [stmt_nodes[r1:r2] for r1, r2 in ranges]
            ):
                yield ranges, to_aunify


def is_any_similar_to_block(checker, duplicate: Set[nodes.NodeNG], candidates):
    def may_be_similar_to_loop(ranges):
        return all(last == first for ((_, last), (first, _)) in zip(ranges, ranges[1:]))

    def all_children_of_one_statement(to_aunify: List[List[nodes.NodeNG]]) -> bool:
        last_ancestors = set(to_aunify[0][-1].node_ancestors())
        for parent in to_aunify[0][0].node_ancestors():
            if not isinstance(parent, nodes.Module) and parent in last_ancestors:
                last_same_type_sibling = parent
                while not isinstance(parent, nodes.FunctionDef) and isinstance(
                    last_same_type_sibling.next_sibling(), type(parent)
                ):
                    last_same_type_sibling = last_same_type_sibling.next_sibling()
                from_ = parent.fromlineno
                to_ = last_same_type_sibling.tolineno
                if all(
                    from_ <= sub_aunify[0].fromlineno and sub_aunify[-1].tolineno <= to_
                    for sub_aunify in to_aunify
                ):
                    return True
        return False

    for this_id in set(candidates.values()):
        this_candidate = [c for c, id_ in candidates.items() if id_ == this_id]
        if may_be_similar_to_loop([r for r, _ in this_candidate]):
            continue

        to_aunify = [list(sub_aunify) for _, sub_aunify in this_candidate]
        if to_aunify[0][0] in duplicate:
            continue

        if all_children_of_one_statement(to_aunify):
            continue

        if similar_to_block(checker, to_aunify):
            duplicate.update(
                {node for sub_aunify in to_aunify for node in get_duplicate_nodes(sub_aunify)}
            )


class NoDuplicateCode(BaseChecker):  # type: ignore
    name = "big-no-duplicate-code"
    msgs = {
        "R6801": (
            # "Lines %i to %i are similar to lines %i through %i. Extract them to a common function.",
            "Extract to a common function (%d repetitions of %d statements).",
            "similar-to-function",
            "",
        ),
        "R6802": (
            "Extract code into loop (%d repetitions of %d statements)",
            "similar-to-loop",
            "",
        ),
        "R6803": (
            "Use existing function %s",
            "similar-to-call",
            "",
        ),
        "R6804": (
            "Extract ifs to ternary",
            "if-to-ternary",
            "",
        ),
        "R6805": (
            "Combine",
            "seq-into-similar",
            "",
        ),
        "R6806": (
            "Extract ifs to variables",
            "if-to-variables",
            "",
        ),
        "R6807": (
            "Move if into block",
            "if-into-block",
            "",
        ),
        "R6808": (
            "Merge with parent loop %s",
            "similar-to-loop-merge",
            "",
        ),
        "R6809": (
            "Extract to a common function (%d repetitions of %d statements).",
            "similar-to-function-in-if",
            "",
        ),
        "R6810": (
            "Use condition directly",
            "if-to-use",
            "",
        ),
        "R6811": (
            "Restructure twisted ifs",
            "twisted-if-to-restructured",
            "",
        ),
        "R6851": (
            "Identical code inside all if's branches, move %d lines %s the if.",
            "identical-before-after-branch",
            "Emitted when identical code starts or ends all branches of an if statement.",
        ),
        "R6852": (
            "Identical code inside %d consecutive ifs, join their conditions using 'or'.",
            "identical-seq-ifs",
            "Emitted when several consecutive if statements have identical bodies and thus can be "
            "joined by or in their conditions.",
        ),
        "R6853": (
            "A complex expression '%s' used repeatedly (on lines %s). Extract it to a local variable.",
            "identical-exprs-to-variable",
            "Emitted when an overly complex expression is used multiple times.",
        ),
        "R6854": (
            "A complex expression '%s' used repeatedly (on lines %s). Extract it to a local variable.",
            "identical-exprs-to-function",
            "Emitted when an overly complex expression is used multiple times.",
        ),
        "R6855": (
            "Identical if branches",
            "identical-if-branches",
            "",
        ),
    }

    def visit_module(self, node: nodes.Module):
        if len(node.body) == 0:
            return

        stmt_nodes = get_statement_nodes(node)
        stmt_to_index = {node: i for i, node in enumerate(stmt_nodes)}

        duplicate = set()
        candidates = {}
        siblings = {}
        for i, fst in candidate_fst(stmt_nodes):
            if fst in duplicate:
                continue

            fst_siblings = get_memoized_siblings(siblings, fst)

            if is_similar_to_loop(self, fst_siblings):
                duplicate.update(get_duplicate_nodes(fst_siblings))
                continue

            any_duplication, inspect_first_if = is_duplicate_in_if(self, fst)
            if any_duplication:
                duplicate.update(
                    get_duplicate_nodes(fst)
                    - (get_duplicate_nodes(fst.body[0]) if inspect_first_if else set())
                )
                continue

            for ranges, to_aunify in get_similar_to_block_candidates(
                self, stmt_nodes, stmt_to_index, siblings, i
            ):
                # TODO or larger?
                id_ = candidates.get((ranges[0], to_aunify[0]), len(candidates))
                candidates[(ranges[0], to_aunify[0])] = id_
                candidates[(ranges[1], to_aunify[1])] = id_

        is_any_similar_to_block(self, duplicate, candidates)


def register(linter: "PyLinter") -> None:
    """This required method auto registers the checker during initialization.
    :param linter: The linter to register the checker to.
    """
    linter.register_checker(NoDuplicateCode(linter))
