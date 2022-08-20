from edulint.options import Option, T, UnionT, ImmutableT
from typing import Optional, Generic
from dataclasses import dataclass


@dataclass(frozen=True)
class Arg(Generic[T]):
    option: Option
    val: T


UnprocessedArg = Arg[Optional[str]]
ProcessedArg = Arg[UnionT]
ImmutableArg = Arg[ImmutableT]
