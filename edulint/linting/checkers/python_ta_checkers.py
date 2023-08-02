# combined from
# https://github.com/pyta-uoft/pyta/blob/683505e2a910c2a252739094593406e4e0f29a85/python_ta/checkers/invalid_for_target_checker.py
# https://github.com/pyta-uoft/pyta/blob/683505e2a910c2a252739094593406e4e0f29a85/python_ta/checkers/one_iteration_checker.py
# https://github.com/pyta-uoft/pyta/blob/683505e2a910c2a252739094593406e4e0f29a85/python_ta/checkers/shadowing_in_comprehension_checker.py
# https://github.com/pyta-uoft/pyta/blob/683505e2a910c2a252739094593406e4e0f29a85/python_ta/checkers/top_level_code_checker.py


from typing import TYPE_CHECKING, Union, List

import re

from astroid import nodes
from pylint.checkers import BaseChecker
from pylint.checkers.base import UpperCaseStyle
from pylint.checkers.utils import only_required_for_messages

if TYPE_CHECKING:
    from pylint.lint import PyLinter

from edulint.linting.checkers.utils import is_main_block


class InvalidForTargetChecker(BaseChecker):
    # name is the same as file name but without _checker part
    name = "invalid_for_target"
    # use dashes for connecting words in message symbol
    msgs = {
        "E9984": (
            'For loop or comprehension variable "%s" should not be a part of a larger object.',
            "invalid-for-target",
            "Used when you have an index variable in a for loop or comprehension"
            "that is in subscript or object attribute form",
        )
    }
    # this is important so that your checker is executed before others
    priority = -1

    INVALID_TARGETS = (nodes.Subscript, nodes.AssignAttr)

    @only_required_for_messages("invalid-for-target")
    def visit_for(self, node: nodes.For) -> None:
        invalid_for_targets = node.target.nodes_of_class(self.INVALID_TARGETS)
        for target in invalid_for_targets:
            self.add_message("invalid-for-target", node=target, args=target.as_string())

    @only_required_for_messages("invalid-for-target")
    def visit_comprehension(self, node: nodes.Comprehension) -> None:
        invalid_for_targets = node.target.nodes_of_class(self.INVALID_TARGETS)
        for target in invalid_for_targets:
            self.add_message("invalid-for-target", node=target, args=target.as_string())


class OneIterationChecker(BaseChecker):
    # name is the same as file name but without _checker part
    name = "one_iteration"
    # use dashes for connecting words in message symbol
    msgs = {
        "E9996": (
            "This loop will only ever run for one iteration",
            "one-iteration",
            "Reported when the loop body always ends the loop in its first iteration "
            '(e.g., by returning or using the "break" keyword).',
        )
    }

    # this is important so that your checker is executed before others
    priority = -1

    # pass in message symbol as a parameter of only_required_for_messages
    @only_required_for_messages("one-iteration")
    def visit_for(self, node: nodes.For) -> None:
        if self._check_one_iteration(node):
            self.add_message("one-iteration", node=node)

    @only_required_for_messages("one-iteration")
    def visit_while(self, node: nodes.While) -> None:
        if self._check_one_iteration(node):
            self.add_message("one-iteration", node=node)

    def _check_one_iteration(self, node: Union[nodes.For, nodes.While]) -> bool:
        """Return whether the given loop is guaranteed to stop after one iteration.
        More precisely, Returns False if there exists a direct predecessor
        block `p` to the start of the loop block `s` such that the
        first statement in `p` is a child node of <node> and that there exists a
        path from `s` to `p.
        Note: For `while` loops, 'start of the loop block' refers to the block with
        the test condition (or the first of the blocks that make up test condition).
        For `for` loops, it refers to the block with the assignment target.
        """
        start = node.target if isinstance(node, nodes.For) else node
        if not hasattr(start, "cfg_block"):
            return False

        preds = start.cfg_block.predecessors

        if preds == []:
            return False

        for pred in preds:
            stmt = pred.source.statements[0]
            if node.parent_of(stmt) and pred.source.reachable:
                if isinstance(node, nodes.For) and stmt is node.iter:
                    continue
                return False
        return True


class ShadowingInComprehensionChecker(BaseChecker):
    name = "shadowing_in_comprehension"
    msgs = {
        "E9988": (
            "Comprehension variable '%s' shadows a variable in an outer scope",
            "shadowing-in-comprehension",
            "Used when there is shadowing inside a comprehension",
        )
    }

    # this is important so that your checker is executed before others
    priority = -1

    @only_required_for_messages("shadowing-in-comprehension")
    def visit_comprehension(self, node: nodes.Comprehension) -> None:
        if isinstance(node.target, nodes.Tuple):
            for target in node.target.elts:
                if (
                    isinstance(target, nodes.Name)
                    and target.name in node.parent.frame().locals
                    and target.name != "_"
                ):
                    args = target.name
                    self.add_message("shadowing-in-comprehension", node=target, args=args)
        elif isinstance(node.target, nodes.AssignName):
            if node.target.name in node.parent.frame().locals and node.target.name != "_":
                args = node.target.name
                self.add_message("shadowing-in-comprehension", node=node.target, args=args)


class TopLevelCodeChecker(BaseChecker):
    name = "top_level_code"
    msgs = {
        "E9992": (
            "Forbidden top-level code found on line %s",
            "forbidden-top-level-code",
            "Used when you write top-level code that is not allowed. "
            "The allowed top-level code includes imports, definitions, and assignments.",
        )
    }

    # this is important so that your checker is executed before others
    priority = -1

    @only_required_for_messages("forbidden-top-level-code")
    def visit_module(self, node: nodes.Module) -> None:
        for statement in node.body:
            if not (
                _is_import(statement)
                or _is_definition(statement)
                or _is_assignment(statement)
                or is_main_block(statement)
            ):
                self.add_message("forbidden-top-level-code", node=statement, args=statement.lineno)


# Helper functions
def _is_import(statement: nodes.NodeNG) -> bool:
    """
    Return whether or not <statement> is an Import or an ImportFrom.
    """
    return isinstance(statement, (nodes.Import, nodes.ImportFrom))


def _is_definition(statement: nodes.NodeNG) -> bool:
    """
    Return whether or not <statement> is a function definition or a class definition.
    """
    return isinstance(statement, (nodes.FunctionDef, nodes.ClassDef))


def _is_constant_assignment(statement: nodes.NodeNG) -> bool:
    """
    Return whether or not <statement> is a constant assignment.
    """
    if not isinstance(statement, nodes.Assign):
        return False

    names: List[str] = []
    for target in statement.targets:
        names.extend(node.name for node in target.nodes_of_class(nodes.AssignName, nodes.Name))

    return all(re.match(UpperCaseStyle.CONST_NAME_RGX, name) for name in names)


def _is_assignment(statement: nodes.NodeNG) -> bool:
    return isinstance(statement, nodes.Assign)


def register(linter: "PyLinter") -> None:
    linter.register_checker(InvalidForTargetChecker(linter))
    linter.register_checker(OneIterationChecker(linter))
    linter.register_checker(ShadowingInComprehensionChecker(linter))
    linter.register_checker(TopLevelCodeChecker(linter))
