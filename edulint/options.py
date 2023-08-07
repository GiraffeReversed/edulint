from typing import List, Any, TypeVar, Optional, Union, Tuple
from enum import Enum


class NumberFromZero(Enum):
    def __new__(cls, *args: Any) -> "NumberFromZero":
        value = len(cls.__members__)
        obj = object.__new__(cls)
        obj._value_ = value
        return obj


T = TypeVar("T")
UnionT = Union[bool, List[str], Optional[str], Optional[int]]
ImmutableT = Union[bool, Tuple[str, ...], Optional[str], Optional[int]]


class Option(NumberFromZero):
    CONFIG = ()
    PYLINT = ()
    FLAKE8 = ()
    ENHANCEMENT = ()
    PYTHON_SPECIFIC = ()
    COMPLEXITY = ()
    ALLOWED_ONECHAR_NAMES = ()
    IB111_WEEK = ()
    NO_FLAKE8 = ()
    IGNORE_INFILE_CONFIG_FOR = ()

    def to_name(self) -> str:
        return self.name.lower().replace("_", "-")

    @staticmethod
    def from_name(option_str: str) -> "Option":
        for option in Option:
            if option.to_name() == option_str.lower():
                return option
        assert False, "no such option: " + option_str

    def __int__(self) -> int:
        return self.value  # type: ignore


DEFAULT_CONFIG = "default"
BASE_CONFIG = "empty"
