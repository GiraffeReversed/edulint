from astroid import nodes  # type: ignore
from typing import TYPE_CHECKING

from pylint.checkers import BaseChecker  # type: ignore
from pylint.checkers.utils import only_required_for_messages

if TYPE_CHECKING:
    from pylint.lint import PyLinter  # type: ignore

from edulint.linting.checkers.utils import get_statements_count
from edulint.linting.analyses.cfg.utils import successors_from_loc
from edulint.linting.analyses.var_events import VarEventType


class NoGlobalVars(BaseChecker):
    name = "no-global-variables"
    msgs = {
        "R6401": (
            "Do not use global variables; you use %s, modifying it for example at line %i.",
            "no-global-vars",
            "Emitted when the code uses global variables.",
        ),
    }

    def visit_module(self, node: nodes.Module):
        if len(node.body) == 0:
            return

        toplevel_vars = {}
        for loc in successors_from_loc(node.body[0].cfg_loc, include_start=True):
            toplevel = loc.node
            if isinstance(toplevel, (nodes.Import, nodes.ImportFrom)):
                continue

            for var, event in toplevel.cfg_loc.var_events.all():
                if var.scope == node and event.type in (VarEventType.ASSIGN, VarEventType.REASSIGN):
                    toplevel_vars[var] = event

        if len(toplevel_vars) == 0:
            return

        for loc in successors_from_loc(
            node.cfg_loc, include_start=True, explore_functions=True, explore_classes=True
        ):
            for var, events in loc.var_events.items():
                if var not in toplevel_vars:
                    continue
                for event in events:
                    if event.type != VarEventType.READ and event.node.parent.scope() != node:
                        self.add_message(
                            "no-global-vars",
                            node=toplevel_vars[var].node,
                            args=(var.name, event.node.lineno),
                        )
                        toplevel_vars.pop(var)
                        break


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
