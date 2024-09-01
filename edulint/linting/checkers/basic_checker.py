from astroid import nodes  # type: ignore
from typing import TYPE_CHECKING

from pylint.checkers import BaseChecker  # type: ignore
from pylint.checkers.utils import only_required_for_messages

if TYPE_CHECKING:
    from pylint.lint import PyLinter  # type: ignore

from edulint.linting.checkers.utils import get_statements_count
from edulint.linting.checkers.modified_listener import ModifiedListener


class NoGlobalVars(BaseChecker):
    name = "no-global-variables"
    msgs = {
        "R6401": (
            "Do not use global variables; you use %s, modifying it for example at line %i.",
            "no-global-vars",
            "Emitted when the code uses global variables.",
        ),
    }

    def __init__(self, linter: "PyLinter"):
        super().__init__(linter)
        self.to_check = {}

    def visit_assignname(self, node: nodes.AssignName) -> None:
        frame = node.frame()
        if not isinstance(frame, nodes.Module):
            return

        if frame not in self.to_check:
            self.to_check[frame] = {}

        if node.name in self.to_check[frame].keys():
            return

        self.to_check[frame][node.name] = node

    def close(self) -> None:
        for frame, vars_ in self.to_check.items():
            listener = ModifiedListener(list(vars_.values()))
            listener.visit(frame)
            for node in vars_.values():
                if listener.was_modified(node, allow_definition=True):
                    nonglobal_modifiers = [
                        n for n in listener.get_all_modifiers(node) if n.scope() != node.scope()
                    ]
                    if nonglobal_modifiers:
                        self.add_message(
                            "no-global-vars",
                            node=node,
                            args=(node.name, nonglobal_modifiers[0].lineno),
                        )


class LongCodeChecker(BaseChecker):
    name = "long-code"
    msgs = {
        "R6701": (
            "Too much code outside of functions or classes (%d which is over %d statements).",
            "long-script",
            "Emitted when there are too many lines of code on the top level that are not import or function or class "
            "definition.",
        ),
        "R6702": (
            "Function '%s' is too long (%d which is over %d statements).",
            "long-function",
            "Emitted when there are too many statements inside a function definition.",
        ),
    }

    @only_required_for_messages("long-script")
    def visit_module(self, node: nodes.Module):
        MAX_SCRIPT = 20

        count = get_statements_count(node, include_defs=False, include_name_main=False)
        if count > MAX_SCRIPT:
            self.add_message("long-script", node=node, args=(count, MAX_SCRIPT))

    @only_required_for_messages("long-function")
    def visit_functiondef(self, node: nodes.FunctionDef):
        MAX_FUNC = 20

        count = get_statements_count(node.body, include_defs=False, include_name_main=False)
        if count > MAX_FUNC:
            self.add_message("long-function", node=node, args=(node.name, count, MAX_FUNC))


def register(linter: "PyLinter") -> None:
    """This required method auto registers the checker during initialization.
    :param linter: The linter to register the checker to.
    """
    linter.register_checker(NoGlobalVars(linter))
    linter.register_checker(LongCodeChecker(linter))
