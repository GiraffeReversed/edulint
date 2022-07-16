from edulint.linters import Linters
from edulint.options import Option
from edulint.config.arg import Arg
from edulint.config.config import Config
from edulint.linting.problem import Problem
from dataclasses import dataclass
from typing import Callable, Optional, Pattern, Match, AnyStr, Dict, Tuple, Set, List
import re


@dataclass
class Tweaker:
    used_options: Set[Option]

    pattern: Pattern[AnyStr]  # type: ignore
    keep: Callable[["Tweaker", Problem, List[Arg]], bool]
    reword: Optional[Callable[["Tweaker", Problem], str]] = None

    def match(self, problem: Problem) -> Optional[Match[AnyStr]]:
        return self.pattern.match(problem.text)

    def should_keep(self, problem: Problem, args: List[Arg]) -> bool:
        return self.keep(self, problem, args)  # type: ignore

    def does_reword(self) -> bool:
        return self.reword is not None

    def get_reword(self, problem: Problem) -> str:
        return self.reword(self, problem) if self.reword else problem.text


def invalid_name_keep(self: Tweaker, problem: Problem, args: List[Arg]) -> bool:
    match = self.match(problem)
    assert match
    if match.group(1).lower() == "module":
        return False

    name = match.group(2)
    style = match.group(3)
    if len(name) == 1 and Config.has_opt_in(args, Option.ALLOWED_ONECHAR_NAMES):
        allowed_names = Config.get_val_from(args, Option.ALLOWED_ONECHAR_NAMES)
        assert allowed_names is not None
        return name not in allowed_names

    if style == "snake_case naming style" and any(ch1.islower() and ch2.isupper() for ch1, ch2 in zip(name, name[1:])):
        return True
    return False


Tweakers = Dict[Tuple[Linters, str], Tweaker]

TWEAKERS = {
    (Linters.PYLINT, "C0103"): Tweaker(  # invalid-name
        set([Option.PYTHON_SPEC, Option.ALLOWED_ONECHAR_NAMES]),
        re.compile(r"^(.*) name \"(.*)\" doesn't conform to (.*)$"),
        invalid_name_keep
    )
}


def get_tweakers() -> Tweakers:
    return TWEAKERS
