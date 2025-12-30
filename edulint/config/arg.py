from edulint.options import Option, T, UnionT, ImmutableT
from typing import Optional, Generic
from dataclasses import dataclass


@dataclass(frozen=True)
class Arg(Generic[T]):
    """Stores option and its value."""

    option: Option
    """
    For possible options, see Configuration in documentation or the packages
    help page (``edulint check -h``).
    """
    val: T
    """
    Value type depends on the option -- different options have different
    value types.
    """


UnprocessedArg = Arg[Optional[str]]
ProcessedArg = Arg[UnionT]
ImmutableArg = Arg[ImmutableT]
