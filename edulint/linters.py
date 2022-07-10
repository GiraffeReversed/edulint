from enum import Enum


class Linters(Enum):
    EDULINT = 0,  # keep defined first
    PYLINT = 1,
    FLAKE8 = 2

    def __str__(self: Enum) -> str:
        return self.name.lower()

    @staticmethod
    def from_str(linter_str: str) -> "Linters":
        for linter in Linters:
            if str(linter) == linter_str.lower():
                return linter
        assert False, "no such linter: " + linter_str
