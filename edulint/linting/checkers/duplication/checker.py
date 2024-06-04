from typing import TYPE_CHECKING

from astroid import nodes  # type: ignore
from pylint.checkers import BaseChecker  # type: ignore

if TYPE_CHECKING:
    from pylint.lint import PyLinter  # type: ignore

from edulint.linting.analyses.antiunify import antiunify, cprint  # noqa: F401
from edulint.linting.analyses.cfg.utils import (
    get_cfg_loc,
    get_stmt_locs,
    syntactic_children_locs_from,
    successors_from_loc,
)
from edulint.linting.checkers.utils import is_block_comment, EXPRESSION_TYPES
from edulint.linting.checkers.duplication.duplicate_if import (
    duplicate_blocks_in_if,
    identical_before_after_branch,
    identical_seq_ifs,
)
from edulint.linting.checkers.duplication.duplicate_sequence import similar_to_loop
from edulint.linting.checkers.duplication.duplicate_block import (
    similar_to_function,
    similar_to_call,
)
from edulint.linting.checkers.duplication.utils import (
    length_mismatch,
    type_mismatch,
    called_aunify_var,
    assignment_to_aunify_var,
    is_duplication_candidate,
    get_loop_repetitions,
)


def candidate_fst(nodes):
    yield from enumerate(nodes)


def candidate_snd(nodes, i):
    fst = nodes[i]
    j = i + 1

    while j < len(nodes) and fst.tolineno >= nodes[j].fromlineno:
        j += 1

    for j in range(j, len(nodes)):
        yield j, nodes[j]


def get_siblings(node):
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


def get_memoized_siblings(siblings, node):
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


def get_stmt_range(stmt_to_index, nodes):
    last_i = stmt_to_index.get(nodes[-1])
    return stmt_to_index[nodes[0]], last_i + 1 if last_i is not None else None


def overlap(stmt_nodes, range1, range2) -> bool:
    first1, last1 = range1
    first2, last2 = range2
    if last1 is None or last2 is None:
        return True

    last_node = stmt_nodes[last1 - 1]
    first_node = stmt_nodes[first2]
    return last_node.tolineno >= first_node.fromlineno


def break_on_stmt(node):
    return isinstance(node, (nodes.Assert, nodes.ClassDef))


def skip_stmt(node):
    return (
        is_block_comment(node)
        or isinstance(node, nodes.Pass)
        or (isinstance(node, (nodes.Import, nodes.ImportFrom)) and node.parent == node.root())
        or (
            isinstance(node, (nodes.Assign, nodes.AugAssign, nodes.AnnAssign))
            and len(node.cfg_loc.uses) == 0
        )
    )


def include_in_stmts(node):
    return not break_on_stmt(node) and not skip_stmt(node)


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
            "Restructure nested ifs",
            "nested-if-to-restructured",
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

        stmt_nodes = sorted(
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
        stmt_to_index = {node: i for i, node in enumerate(stmt_nodes)}

        duplicate = set()
        candidates = {}
        siblings = {}
        for i, fst in candidate_fst(stmt_nodes):
            if fst in duplicate:
                continue

            if isinstance(fst, nodes.If):
                any_message1 = identical_before_after_branch(self, fst)
                any_message2 = not any_message1 and duplicate_blocks_in_if(self, fst)

                if any_message1 or any_message2:
                    duplicate.update(
                        {
                            stmt_loc.node
                            for loc in syntactic_children_locs_from(fst.cfg_loc, fst)
                            for stmt_loc in get_stmt_locs(loc)
                            if stmt_loc is not None
                        }
                        # do not suggest more changes in a duplicate-if block,
                        # other than moving identical before-after branch code
                        - (
                            {
                                stmt_loc.node
                                for loc in syntactic_children_locs_from(
                                    fst.body[0].cfg_loc, fst.body
                                )
                                for stmt_loc in get_stmt_locs(loc)
                                if stmt_loc is not None
                            }
                            if not any_message2
                            else set()
                        )
                    )
                    continue

            fst_siblings = get_memoized_siblings(siblings, fst)

            if (
                (
                    self.linter.is_message_enabled("similar-to-loop")
                    or self.linter.is_message_enabled("similar-to-loop-merge")
                )
                and len(fst_siblings) >= 3
                and not any(isinstance(node, nodes.FunctionDef) for node in fst_siblings)
            ):
                for end, to_aunify in get_loop_repetitions(fst_siblings):
                    if not is_duplication_candidate(to_aunify):
                        continue
                    if similar_to_loop(self, to_aunify):
                        duplicate.update(
                            {
                                stmt_loc.node
                                for loc in syntactic_children_locs_from(
                                    get_cfg_loc(fst),
                                    [n for n in fst_siblings],
                                )
                                for stmt_loc in get_stmt_locs(loc)
                                if stmt_loc is not None
                            }
                        )
                        break

                if fst in duplicate:
                    continue

            if isinstance(fst, nodes.If):
                # TODO only if similar-to-loop would detect nothing?
                any_message, last_if = identical_seq_ifs(self, fst)

                if any_message:
                    for sibling in fst_siblings:
                        duplicate.update(
                            {
                                stmt_loc.node
                                for loc in syntactic_children_locs_from(sibling.cfg_loc, sibling)
                                for stmt_loc in get_stmt_locs(loc)
                                if stmt_loc is not None
                            }
                        )
                        if sibling == last_if or sibling in last_if.node_ancestors():
                            break
                    continue

            if not self.linter.is_message_enabled(
                "similar-to-function"
            ) and not self.linter.is_message_enabled("similar-to-call"):
                continue

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
                        # TODO or larger?
                        id_ = candidates.get((ranges[0], to_aunify[0]), len(candidates))
                        candidates[(ranges[0], to_aunify[0])] = id_
                        candidates[(ranges[1], to_aunify[1])] = id_
                        break

        for this_id in set(candidates.values()):
            ranges = [range for (range, _), id_ in candidates.items() if id_ == this_id]
            if all(last == first for ((_, last), (first, _)) in zip(ranges, ranges[1:])):
                continue

            to_aunify = [
                list(sub_aunify) for (_, sub_aunify), id_ in candidates.items() if id_ == this_id
            ]
            if to_aunify[0][0] in duplicate:
                continue

            all_children_of_one_if = False
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
                        all_children_of_one_if = True
                        break
            if all_children_of_one_if:
                continue

            result = antiunify(
                to_aunify,
                stop_on=lambda avars: length_mismatch(avars)
                or type_mismatch(
                    avars, allowed_mismatches=[{nodes.Name, t} for t in EXPRESSION_TYPES]
                )
                or called_aunify_var(avars),
                stop_on_after_renamed_identical=lambda avars: assignment_to_aunify_var(avars),
            )
            if result is None:
                continue
            core, avars = result

            if all(isinstance(vals[0], nodes.FunctionDef) for vals in to_aunify):
                continue  # TODO hint use common helper function
            any_message1 = similar_to_call(self, to_aunify, core, avars)
            any_message2 = not any_message1 and similar_to_function(self, to_aunify, core, avars)

            if any_message1 or any_message2:
                duplicate.update(
                    {
                        stmt_loc.node
                        for sub_aunify in to_aunify
                        for loc in syntactic_children_locs_from(sub_aunify[0].cfg_loc, sub_aunify)
                        for stmt_loc in get_stmt_locs(loc)
                        if stmt_loc is not None
                    }
                )


def register(linter: "PyLinter") -> None:
    """This required method auto registers the checker during initialization.
    :param linter: The linter to register the checker to.
    """
    linter.register_checker(NoDuplicateCode(linter))
