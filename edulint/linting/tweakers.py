from edulint.linters import Linter
from edulint.options import Option
from edulint.config.arg import ImmutableArg
from edulint.linting.problem import Problem
from dataclasses import dataclass
from typing import Callable, Optional, Pattern, Match, AnyStr, Dict, Tuple, Set, List
import re


@dataclass
class Tweaker:
    used_options: Set[Option]

    pattern: Pattern[AnyStr]  # type: ignore
    keep: Callable[["Tweaker", Problem, List[ImmutableArg]], bool] = lambda _t, _p, _a: True
    reword: Optional[Callable[["Tweaker", Problem], str]] = None

    def match(self, problem: Problem) -> Match[str]:
        match = self.pattern.match(problem.text)
        assert match is not None
        return match

    def should_keep(self, problem: Problem, args: List[ImmutableArg]) -> bool:
        return self.keep(self, problem, args)

    def does_reword(self) -> bool:
        return self.reword is not None

    def get_reword(self, problem: Problem) -> str:
        return self.reword(self, problem) if self.reword else problem.text


def invalid_name_keep(self: Tweaker, problem: Problem, args: List[ImmutableArg]) -> bool:
    match = self.match(problem)
    if match.group(1).lower() == "module":
        return False

    name = match.group(2)
    style = match.group(3)

    if style == "snake_case naming style":
        return name[0].isupper() or any(
            ch1.islower() and ch2.isupper() for ch1, ch2 in zip(name, name[1:])
        )

    if style == "PascalCase naming style":
        return name[0].islower() or "_" in name

    return True


def disallowed_name_keep(self: Tweaker, problem: Problem, args: List[ImmutableArg]) -> bool:
    if (
        len(args) == 1
        and args[0].option == Option.ALLOWED_ONECHAR_NAMES
        and args[0].val is not None
    ):
        assert isinstance(args[0].val, str)
        allowed_onechar_names = args[0].val
    else:
        allowed_onechar_names = ""

    match = self.match(problem)
    name = match.group(1)

    return len(name) != 1 or name not in allowed_onechar_names


def disallowed_name_reword(self: Tweaker, problem: Problem) -> str:
    name = self.match(problem).group(1)
    if len(name) == 1:
        return f'Disallowed single-character variable name "{name}", choose a more descriptive name'
    return problem.text


def consider_using_in_reword(self: Tweaker, problem: Problem) -> str:
    match = self.match(problem)

    groups = match.groups()
    start = groups[0]
    outer_quote = groups[2]
    vals = groups[5].split(", ")
    assert vals

    if all(val.count("(") == val.count(")") for val in vals) and all(
        v and v[0] == v[-1] and v[0] in "\"'" and len(v) == 3 for v in vals
    ):
        inner_quote = vals[0][0]
        return (
            start + inner_quote + "".join(v.strip("\"'") for v in vals) + inner_quote + outer_quote
        )

    return start + f"({', '.join(vals)})" + outer_quote


def unused_import_keep(self: Tweaker, problem: Problem, args: List[ImmutableArg]) -> bool:
    match = self.match(problem)
    return not match.group(1).startswith("ib111")


def no_repeated_op_keep(self: Tweaker, problem: Problem, args: List[ImmutableArg]) -> bool:
    assert len(args) == 1

    if "enhancement" in args[0].val:
        return True

    match = self.match(problem)
    expr = match.group(1)
    return bool(args[0].val) or expr.count("*") > 1


def superfluous_parens_keep(self: Tweaker, problem: Problem, args: List[ImmutableArg]) -> bool:
    match = self.match(problem)
    keyword = match.group(1).strip("'\"")

    return keyword.lower() != "not"


def redefined_builtin_keep(self: Tweaker, problem: Problem, args: List[ImmutableArg]) -> bool:
    match = self.match(problem)
    redefined_builtin = match.group(1).strip("'\"")

    assert len(args) == 1 and args[0].option == Option.DISALLOWED_BUILTIN_NAMES
    disallowed_builtin_names = args[0].val

    return not disallowed_builtin_names or redefined_builtin in disallowed_builtin_names


def singleton_bool_comparison_reword(self: Tweaker, problem: Problem) -> bool:
    match = self.match(problem)
    return "".join(match.groups())


Tweakers = Dict[Tuple[Linter, str], Tweaker]

TWEAKERS = {
    (Linter.PYLINT, "C0103"): Tweaker(  # invalid-name
        set(), re.compile(r"^(.*) name \"(.*)\" doesn't conform to (.*)$"), invalid_name_keep
    ),
    (Linter.PYLINT, "C0104"): Tweaker(  # disallowed-name
        set([Option.ALLOWED_ONECHAR_NAMES]),
        re.compile(r"Disallowed name \"(.*)\""),
        disallowed_name_keep,
        disallowed_name_reword,
    ),
    (Linter.PYLINT, "R1714"): Tweaker(  # consider-using-in
        set(),
        re.compile(
            r"^(Consider merging these comparisons with ['\"]in['\"] (to|by using) "
            r"(\"|\')([^\s]*)( not)? in )\((.+)\)(\"|\')"
        ),
        reword=consider_using_in_reword,
    ),
    (Linter.FLAKE8, "F401"): Tweaker(  # module imported but unused
        set(), re.compile("'(.*)' imported but unused"), unused_import_keep
    ),
    (Linter.PYLINT, "R6607"): Tweaker(  # no-repeated-op
        set([Option.SET_GROUPS]),
        re.compile(r"^Use [^ ]* instead of repeated [^ ]* in ([^\.]*)."),
        no_repeated_op_keep,
    ),
    (Linter.PYLINT, "C0325"): Tweaker(  # superfluous-parens
        set(),
        re.compile(r"Unnecessary parens after (.*) keyword"),
        superfluous_parens_keep,
    ),
    (Linter.PYLINT, "W0622"): Tweaker(  # redefined-builtin
        set([Option.DISALLOWED_BUILTIN_NAMES]),
        re.compile(r"^Redefining built-in (.*)"),
        redefined_builtin_keep,
    ),
    (Linter.FLAKE8, "E712"): Tweaker(  # singleton bool comparison
        set(),
        re.compile(r"(comparison to (?:True|False) should be )'if cond is .*' or (.*)"),
        reword=singleton_bool_comparison_reword,
    ),
}


def get_tweakers() -> Tweakers:
    return TWEAKERS
