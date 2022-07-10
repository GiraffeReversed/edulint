from edulint.linters import Linters
from edulint.linting.problem import Problem
from dataclasses import dataclass
from typing import Callable, Optional, Pattern, Match, AnyStr, Dict, Tuple
import re


@dataclass
class Tweaker:
    pattern: Pattern[AnyStr]  # type: ignore
    keep: Callable[["Tweaker", Problem], bool]
    reword: Optional[Callable[["Tweaker", Problem], str]] = None

    def match(self, problem: Problem) -> Optional[Match[AnyStr]]:
        return self.pattern.match(problem.text)

    def should_keep(self, problem: Problem) -> bool:
        return self.keep(self, problem)  # type: ignore

    def does_reword(self) -> bool:
        return self.reword is not None

    def get_reword(self, problem: Problem) -> str:
        return self.reword(self, problem) if self.reword else problem.text


def invalid_name_keep(self: Tweaker, problem: Problem) -> bool:
    match = self.match(problem)
    assert match
    if match.group(1).lower() == "module":
        return False

    name = match.group(2)
    style = match.group(3)
    if style == "snake_case naming style" and any(ch1.islower() and ch2.isupper() for ch1, ch2 in zip(name, name[1:])):
        return True
    return False


Tweakers = Dict[Tuple[Linters, str], Tweaker]

TWEAKERS = {
    (Linters.PYLINT, "C0103"): Tweaker(  # invalid-name
        re.compile(r"^(.*) name \"(.*)\" doesn't conform to (.*)$"),
        invalid_name_keep
    )
}


def get_tweakers() -> Tweakers:
    return TWEAKERS
