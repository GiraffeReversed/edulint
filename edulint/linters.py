from enum import Enum, auto
from edulint.options import Option


class Linter(Enum):
    EDULINT = auto()
    PYLINT = auto()
    FLAKE8 = auto()

    def __str__(self: Enum) -> str:
        return self.name.lower()

    @staticmethod
    def from_name(linter_str: str) -> "Linter":
        for linter in Linter:
            if str(linter) == linter_str.lower():
                return linter
        assert False, "no such linter: " + linter_str

    def to_name(self) -> str:
        return str(self)

    @classmethod
    def from_option(cls, option: Option) -> "Linter":
        return cls.from_name(option.to_name())

    def to_option(self) -> Option:
        return Option.from_name(self.to_name())
