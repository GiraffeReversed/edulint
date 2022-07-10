from edulint.linters import Linters
from dataclasses import dataclass


@dataclass(frozen=True)
class Arg:
    to: Linters
    val: str
