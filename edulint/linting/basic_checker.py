from astroid import nodes  # type: ignore
from typing import TYPE_CHECKING, Optional

from pylint.checkers import BaseChecker  # type: ignore

if TYPE_CHECKING:
    from pylint.lint import PyLinter  # type: ignore


class OnecharNames(BaseChecker):  # type: ignore

    name = "only-allowed-onechar-names"
    msgs = {
        "R6001": (
            "Disallowed single-character variable name \"%s\", choose a more descriptive name.",
            "disallowed-onechar-name",
            "Only allowed one-character names can be used.",
        ),
    }
    options = (
        (
            "allowed-onechar-names",
            {
                "default": "",
                "type": "choice",
                "metavar": "<chars>",
                "help": "List allowed one-character names.",
            },
        ),
    )

    def __init__(self, linter: Optional["PyLinter"] = None) -> None:
        super().__init__(linter)

    def visit_assignname(self, node: nodes.AssignName) -> None:
        name = node.name
        if len(name) == 1 and name not in self.linter.config.allowed_onechar_names:
            self.add_message(
                "disallowed-onechar-name",
                node=node,
                args=(name))


def register(linter: "PyLinter") -> None:
    """This required method auto registers the checker during initialization.
    :param linter: The linter to register the checker to.
    """
    linter.register_checker(OnecharNames(linter))
