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
    }

    @only_required_for_messages("duplicate-if-branches")
    def visit_if(self, node: nodes.If) -> None:

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

        def get_line_difference(branches, forward=True) -> int:
            stmts_difference = get_stmts_difference(branches, forward)
            reference = branches[0]

            if stmts_difference == 0:
                return 0

            first = reference[0 if forward else -stmts_difference]
            last = reference[stmts_difference - 1 if forward else -1]
            assert first.fromlineno <= last.fromlineno

            return last.tolineno - first.fromlineno + 1

        if not node.orelse or is_parents_elif(node):
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
            self.add_message("duplicate-if-branches", node=node, args=(same_suffix_len, "after"))


def register(linter: "PyLinter") -> None:
    """This required method auto registers the checker during initialization.
    :param linter: The linter to register the checker to.
    """
    linter.register_checker(NoDuplicateCode(linter))
