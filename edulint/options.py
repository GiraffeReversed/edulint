from dataclasses import dataclass
from typing import Dict, List, Tuple
from enum import Enum, auto


class Option(Enum):
    PYLINT = auto()
    FLAKE8 = auto()
    ENHANCEMENT = auto()
    PYTHON_SPEC = auto()
    ALLOWED_ONECHAR_NAMES = auto()

    def to_name(self) -> str:
        return self.name.lower().replace("_", "-")


class TakesVal(Enum):
    YES = auto()
    NO = auto()
    OPTIONAL = auto()


@dataclass
class OptionParse:
    option: Option
    name: str
    help_: str
    takes_val: TakesVal


OPTIONS: List[Tuple[Option, str, TakesVal]] = [
    (
        Option.PYLINT,
        "arguments to be passed to pylint",
        TakesVal.YES
    ),
    (
        Option.FLAKE8,
        "arguments to be passed to flake8",
        TakesVal.YES
    ),
    (
        Option.ENHANCEMENT,
        "enable checking for ways to improve the code further",
        TakesVal.NO
    ),
    (
        Option.PYTHON_SPEC,
        "enable checking for ways to improve the code with Python-specific constructions",
        TakesVal.NO
    ),
    (
        Option.ALLOWED_ONECHAR_NAMES,
        "only listed characters are allowed to be variable names of length one",
        TakesVal.YES
    ),
]


def get_option_parses() -> Dict[Option, OptionParse]:
    return {option: OptionParse(option, option.to_name(), help_, takes_val) for option, help_, takes_val in OPTIONS}


def get_name_to_option(option_parses: Dict[Option, OptionParse]) -> Dict[str, Option]:
    return {parse.name: opt for opt, parse in option_parses.items()}
