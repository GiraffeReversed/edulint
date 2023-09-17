from .linters import Linter
from .config.config import ImmutableConfig, get_config_one, get_config_many
from .linting.problem import Problem
from .linting.linting import lint_one, lint_many
from .explanations import get_explanations

__all__ = [
    "Linter",
    "ImmutableConfig",
    "get_config_one",
    "get_config_many",
    "Problem",
    "lint_one",
    "lint_many",
    "get_explanations",
]

__version__ = "3.2.1"
__version_info__ = tuple(map(int, __version__.split(".")))
