from edulint.problem import Problem
from dataclasses import dataclass
from typing import Callable, Optional, Pattern, AnyStr
import re


@dataclass
class Tweaker:
    pattern: Pattern[AnyStr]
    keep: Callable[["Tweaker", Problem], bool]
    reword: Optional[Callable[["Tweaker", Problem], str]] = None

    def match(self, problem: Problem) -> Pattern[AnyStr]:
        return self.pattern.match(problem.text)

    def should_keep(self, problem: Problem) -> bool:
        return self.keep(self, problem)

    def does_reword(self) -> bool:
        return self.reword is not None

    def get_reword(self, problem: Problem) -> str:
        return self.reword(self, problem) if self.reword else problem.text


def invalid_name_keep(self: Tweaker, problem: Problem):
    match = self.match(problem)
    assert match
    if match.group(1).lower() == "module":
        return False

    name = match.group(2)
    style = match.group(3)
    if style == "snake_case naming style" and any(ch1.islower() and ch2.isupper() for ch1, ch2 in zip(name, name[1:])):
        return True
    return False


TWEAKERS = {
    "pylint_C0103": Tweaker(  # invalid-name
        re.compile(r"^(.*) name \"(.*)\" doesn't conform to (.*)$"),
        invalid_name_keep
    )
}
