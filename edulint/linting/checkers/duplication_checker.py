from astroid import nodes  # type: ignore
from typing import TYPE_CHECKING, Optional, Tuple, List

from pylint.checkers import BaseChecker  # type: ignore
from pylint.checkers.utils import only_required_for_messages

if TYPE_CHECKING:
    from pylint.lint import PyLinter  # type: ignore

from edulint.linting.checkers.utils import is_parents_elif


class NoDuplicateCode(BaseChecker): # type: ignore
    name = "no-duplicate-code"
    msgs = {
        "R6502": (
            "Identical code inside all if's branches, move %d lines %s the if.",
            "duplicate-if-branches",
            "Emitted when identical code starts or ends all branches of an if statement."
        ),
        "R6503": (
            "Identical code inside %d consecutive ifs, join their conditions using 'or'.",
            "duplicate-seq-ifs",
            "Emitted when several consecutive if statements have identical bodies and thus can be "
            "joined by or in their conditions."
        ),
    }

    @only_required_for_messages("duplicate-if-branches", "duplicate-seq-ifs")
    def visit_if(self, node: nodes.If) -> None:
        self.duplicate_if_branches(node)
        self.duplicate_seq_ifs(node)

    def duplicate_if_branches(self, node: nodes.If) -> None:

        def extract_branch_bodies(node: nodes.If) -> Optional[List[nodes.NodeNG]]:
            branches = [node.body]
            current = node
            while current.has_elif_block():
                elif_ = current.orelse[0]
                if not elif_.orelse:
                    return None

                branches.append(elif_.body)
                current = elif_
            branches.append(current.orelse)
            return branches

        def get_stmts_difference(branches, forward) -> int:
            reference = branches[0]
            compare = branches[1:]
            for i in range(min(map(len, branches))):
                for branch in compare:
                    index = i if forward else -i - 1
                    if reference[index].as_string() != branch[index].as_string():
                        return i
            return i + 1

        def get_lines_between(first: nodes.NodeNG, last: nodes.NodeNG, including_last: bool) -> int:
            assert first.fromlineno <= last.fromlineno

            if including_last:
                return last.tolineno - first.fromlineno + 1
            return last.fromlineno - first.fromlineno

        def get_line_difference(branches, forward=True) -> int:
            stmts_difference = get_stmts_difference(branches, forward)
            reference = branches[0]

            if stmts_difference == 0:
                return 0

            first = reference[0 if forward else -stmts_difference]
            last = reference[stmts_difference - 1 if forward else -1]

            return get_lines_between(first, last, including_last=True)

        if not node.orelse or (is_parents_elif(node)):
            return

        branches = extract_branch_bodies(node)
        if branches is None:
            return

        same_prefix_len = get_line_difference(branches, forward=True)
        if same_prefix_len >= 1:
            self.add_message("duplicate-if-branches", node=node, args=(same_prefix_len, "before"))
            if same_prefix_len == branches[0][-1].tolineno - branches[0][0].fromlineno + 1:
                return

        same_suffix_len = get_line_difference(branches, forward=False)
        if same_suffix_len >= 1:
            # allow early returns
            if same_suffix_len == 1 and isinstance(branches[0][-1], nodes.Return):
                i = 0
                while len(branches[i]) == 1:
                    i += 1
                branches = branches[i:]
                if len(branches) < 2:
                    return
            defect_node = branches[0][-1].parent

            # disallow breaking up coherent segments
            if same_suffix_len / (min(
                map(lambda branch: get_lines_between(branch[0], branch[-1], including_last=True), branches)
            ) - same_prefix_len) < 1/2: # TODO extract into parameter
                return

            self.add_message("duplicate-if-branches", node=defect_node, args=(same_suffix_len, "after"))

    def duplicate_seq_ifs(self, node: nodes.If) -> None:

        """
        returns False iff elifs end with else
        """
        def extract_from_elif(node: nodes.If, seq_ifs: List[List[nodes.NodeNG]]) -> bool:
            if len(node.orelse) > 0 and not node.has_elif_block():
                return False

            current = node
            while current.has_elif_block():
                elif_ = current.orelse[0]
                seq_ifs.append(elif_)
                if len(elif_.orelse) > 0 and not elif_.has_elif_block():
                    return False
                current = elif_
            return True

        def extract_from_siblings(node: nodes.If, seq_ifs: List[List[nodes.NodeNG]]) -> List[List[nodes.NodeNG]]:
            sibling = node.next_sibling()
            while sibling is not None and isinstance(sibling, nodes.If):
                new = []
                if not extract_from_elif(sibling, new):
                    return
                seq_ifs.append(sibling)
                seq_ifs.extend(new)
                sibling = sibling.next_sibling()
            return seq_ifs

        def same_ifs_count(seq_ifs: List[List[nodes.NodeNG]], start: int) -> int:
            reference = seq_ifs[start].body
            for i in range(start + 1, len(seq_ifs)):
                # do not suggest join of elif and sibling
                if seq_ifs[start].parent not in seq_ifs[i].node_ancestors():
                    return i - start

                compared = seq_ifs[i].body
                if len(reference) != len(compared):
                    return i - start
                for j in range(len(reference)):
                    if reference[j].as_string() != compared[j].as_string():
                        return i - start
            return len(seq_ifs) - start


        prev_sibling = node.previous_sibling()
        if is_parents_elif(node) or (isinstance(prev_sibling, nodes.If) and extract_from_elif(prev_sibling, [])):
            return

        seq_ifs = [node]

        if not extract_from_elif(node, seq_ifs):
            return
        extract_from_siblings(node, seq_ifs)

        if len(seq_ifs) == 1:
            return

        i = 0
        while i < len(seq_ifs) - 1:
            count = same_ifs_count(seq_ifs, i)
            if count > 1:
                self.add_message("duplicate-seq-ifs", node=seq_ifs[i], args=(count,))
            i += count

def register(linter: "PyLinter") -> None:
    """This required method auto registers the checker during initialization.
    :param linter: The linter to register the checker to.
    """
    linter.register_checker(NoDuplicateCode(linter))
