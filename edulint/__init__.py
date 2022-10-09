from .linters import Linter
from .config.config import Config
from .linting.problem import Problem
from .linting.linting import lint_one, lint_many

__all__ = ["Linter", "Config", "Problem", "lint_one", "lint_many"]

__version__ = "1.0.0"
__version_info__ = tuple(map(int, __version__.split(".")))
