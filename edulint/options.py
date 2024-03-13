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
    CONFIG_FILE = ()
    PYLINT = ()
    FLAKE8 = ()
    ALLOWED_ONECHAR_NAMES = ()
    DISALLOWED_BUILTIN_NAMES = ()
    NO_FLAKE8 = ()
    IGNORE_INFILE_CONFIG_FOR = ()
    EXPORT_GROUPS = ()
    SET_GROUPS = ()
    LANGUAGE_FILE = ()

    def to_name(self) -> str:
        return self.name.lower().replace("_", "-")

    @staticmethod
    def safe_from_name(option_str: str) -> Optional["Option"]:
        aliased = OPTION_ALIASES.get(option_str.lower())
        if aliased is not None:
            return aliased

        for option in Option:
            if option.to_name() == option_str.lower():
                return option
        return None

    @staticmethod
    def from_name(option_str: str) -> "Option":
        option = Option.safe_from_name(option_str)
        if option is not None:
            return option

        assert False, "no such option: " + option_str

    def __int__(self) -> int:
        return self.value  # type: ignore


OPTION_ALIASES = {"config": Option.CONFIG_FILE}

DEFAULT_CONFIG = "default"
BASE_CONFIG = "empty"
