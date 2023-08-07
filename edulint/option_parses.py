from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Callable
from enum import Enum, auto
from edulint.options import Option, UnionT, T, DEFAULT_CONFIG


class TakesVal(Enum):
    YES = auto()
    NO = auto()
    OPTIONAL = auto()


class MultivaluedEnum(Enum):
    def __new__(cls, *args: Any, **kwds: Any) -> Any:
        value = len(cls.__members__) + 1
        obj = object.__new__(cls)
        obj._value_ = value
        return obj


class Type(MultivaluedEnum):
    @staticmethod
    def _to_bool_val(val: Optional[str]) -> bool:
        return val is None or val in ("true", "on")

    @staticmethod
    def _to_list_val(val: Optional[str]) -> List[str]:
        return [val] if val is not None else []

    @staticmethod
    def _to_str_val(val: Optional[str]) -> Optional[str]:
        return val

    @staticmethod
    def _to_int_val(val: Optional[str]) -> Optional[int]:
        return int(val) if val is not None and val.isdecimal() else None

    def __init__(self, _: Enum, convert: Callable[[Optional[str]], UnionT]):
        self.convert: Callable[[Optional[str]], UnionT] = convert.__func__  # type: ignore

    def __call__(self, arg: Optional[str]) -> UnionT:
        return self.convert(arg)

    BOOL = (auto(), _to_bool_val)
    LIST = (auto(), _to_list_val)
    STR = (auto(), _to_str_val)
    INT = (auto(), _to_int_val)


class Combine(MultivaluedEnum):
    @staticmethod
    def _keep_right_combine(_lt: T, rt: T) -> T:
        return rt

    @staticmethod
    def _append_combine(lt: List[T], rt: T) -> List[T]:
        return lt + [rt]

    @staticmethod
    def _extend_combine(lt: List[T], rt: List[T]) -> List[T]:
        return lt + rt

    def __init__(self, _: Enum, combine: Callable[[UnionT, UnionT], UnionT]):
        self.combine: Callable[[UnionT, UnionT], UnionT] = combine.__func__  # type: ignore

    def __call__(self, lt: UnionT, rt: UnionT) -> UnionT:
        return self.combine(lt, rt)

    REPLACE = (auto(), _keep_right_combine)
    EXTEND = (auto(), _extend_combine)


@dataclass
class OptionParse:
    option: Option
    help_: str
    takes_val: TakesVal
    default: UnionT
    convert: Type
    combine: Combine


OPTIONS: List[OptionParse] = [
    OptionParse(
        Option.CONFIG,
        "config file to use for the linting (packaged name, local path or remote)",
        TakesVal.YES,
        DEFAULT_CONFIG,
        Type.STR,
        Combine.REPLACE,
    ),
    OptionParse(
        Option.PYLINT,
        "arguments to be passed to pylint (formatted to be passed through command line)",
        TakesVal.YES,
        [],
        Type.LIST,
        Combine.EXTEND,
    ),
    OptionParse(
        Option.FLAKE8,
        "arguments to be passed to flake8 (formatted to be passed through command line)",
        TakesVal.YES,
        [],
        Type.LIST,
        Combine.EXTEND,
    ),
    OptionParse(
        Option.ENHANCEMENT,
        "enable checking for ways to improve the code further",
        TakesVal.NO,
        False,
        Type.BOOL,
        Combine.REPLACE,
    ),
    OptionParse(
        Option.PYTHON_SPECIFIC,
        "enable checking for ways to improve the code with Python-specific constructions",
        TakesVal.NO,
        False,
        Type.BOOL,
        Combine.REPLACE,
    ),
    OptionParse(
        Option.COMPLEXITY,
        "enable checking for overly complicated pieces of code",
        TakesVal.NO,
        False,
        Type.BOOL,
        Combine.REPLACE,
    ),
    OptionParse(
        Option.ALLOWED_ONECHAR_NAMES,
        "only listed characters are allowed to be variable names of length one",
        TakesVal.YES,
        None,
        Type.STR,
        Combine.REPLACE,
    ),
    OptionParse(
        Option.IB111_WEEK,
        "set which week's limitation should be applied",
        TakesVal.YES,
        None,
        Type.INT,
        Combine.REPLACE,
    ),
    OptionParse(
        Option.NO_FLAKE8, "turn off flake8", TakesVal.NO, False, Type.BOOL, Combine.REPLACE
    ),
]

OLD_NAMES = {"python-spec": Option.PYTHON_SPECIFIC}


def get_option_parses() -> Dict[Option, OptionParse]:
    return {parse.option: parse for parse in OPTIONS}


def get_name_to_option(option_parses: Dict[Option, OptionParse]) -> Dict[str, Option]:
    from_options = {parse.option.to_name(): opt for opt, parse in option_parses.items()}
    from_options.update(OLD_NAMES)
    return from_options
