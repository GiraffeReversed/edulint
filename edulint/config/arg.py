from edulint.options import Option
from typing import Optional
from dataclasses import dataclass


@dataclass(frozen=True)
class Arg:
    option: Option
    val: Optional[str] = None
