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
    return style != "snake_case naming style" \
        or any(ch1.islower() and ch2.isupper() for ch1, ch2 in zip(name, name[1:]))


def disallowed_name_keep(self: Tweaker, problem: Problem, args: List[ImmutableArg]) -> bool:
    if len(args) == 1 and args[0].option == Option.ALLOWED_ONECHAR_NAMES and args[0].val is not None:
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
        return f"Disallowed single-character variable name \"{name}\", choose a more descriptive name"
    return problem.text


def consider_using_in_reword(self: Tweaker, problem: Problem) -> str:
    match = self.match(problem)

    groups = match.groups()
    start = groups[0]
    outer_quote = groups[1]
    vals = groups[4].split(", ")
    assert vals

    if all(v and v[0] == v[-1] and v[0] in "\"\'" and len(v) == 3 for v in vals):
        inner_quote = vals[0][0]
        return start + inner_quote + "".join(v.strip("\"\'") for v in vals) + inner_quote + outer_quote

    return problem.text


def _get_if_condition(filename: str, line: int) -> str:
    line -= 1  # -1 adjusts for indexing from 0
    with open(filename) as f:
        lines = f.readlines()
        result = [lines[line].strip()]
        while result[-1][-1] == "\\":
            result[-1] = result[-1].strip("\\ ")
            line += 1
            result.append(lines[line].strip())
        return " ".join(result)


def simplifiable_if_statement_reword(self: Tweaker, problem: Problem) -> str:
    if_line = _get_if_condition(problem.path, problem.line)
    if not if_line.startswith("if "):
        return problem.text
    if_line = if_line[len("if "):].strip(":")

    match = self.match(problem)
    return problem.text[:match.start(1)] + if_line + problem.text[match.end(1):]


def _get_if_expression(problem: Problem) -> str:
    with open(problem.path) as f:
        selected_lines = f.readlines()[problem.line - 1:problem.end_line]
    selected_lines[0] = selected_lines[0][problem.column:]  # no -1, columns indexed from 0

    if problem.line == problem.end_line:
        assert problem.end_column is not None
        selected_lines[-1] = selected_lines[-1][:problem.end_column - problem.column]
    else:
        selected_lines[-1] = selected_lines[-1][:problem.end_column]

    return " ".join(line.strip(" \t\n\\") for line in selected_lines)


def simplifiable_if_expression_reword(self: Tweaker, problem: Problem) -> str:
    if_expr = _get_if_expression(problem)
    if_expr_match = re.match(r"(?:True|False) *if *(.*?) *else *(?:True|False)", if_expr)
    if not if_expr_match:
        return problem.text

    match = self.match(problem)
    return problem.text[:match.start(1)] + if_expr_match.group(1) + problem.text[match.end(1):]


def unused_import_keep(self: Tweaker, problem: Problem, args: List[ImmutableArg]) -> bool:
    match = self.match(problem)
    return not match.group(1).startswith("ib111")


Tweakers = Dict[Tuple[Linter, str], Tweaker]

TWEAKERS = {
    (Linter.PYLINT, "C0103"): Tweaker(  # invalid-name
        set(),
        re.compile(r"^(.*) name \"(.*)\" doesn't conform to (.*)$"),
        invalid_name_keep
    ),
    (Linter.PYLINT, "C0104"): Tweaker(  # disallowed-name
        set([Option.ALLOWED_ONECHAR_NAMES]),
        re.compile(r"Disallowed name \"(.*)\""),
        disallowed_name_keep,
        disallowed_name_reword
    ),
    (Linter.PYLINT, "R1714"): Tweaker(  # consider-using-in
        set(),
        re.compile(
            r"^(Consider merging these comparisons with \"in\" to "
            r"(\"|\')([^\s]*)( not)? in )\(([^\)]+)\)(\"|\')"
        ),
        reword=consider_using_in_reword
    ),
    (Linter.PYLINT, "R1703"): Tweaker(  # simplifiable-if-statement
        set(),
        re.compile(
            r"^The if statement can be replaced with '.*?((?:bool\()?test\)?)'"
        ),
        reword=simplifiable_if_statement_reword
    ),
    (Linter.PYLINT, "R1719"): Tweaker(  # simplifiable-if-expression
        set(),
        re.compile(
            r"^The if expression can be replaced with '.*?((?:bool\()?test\)?)'"
        ),
        reword=simplifiable_if_expression_reword
    ),
    (Linter.FLAKE8, "F401"): Tweaker(  # module imported but unused
        set(),
        re.compile("'(.*)' imported but unused"),
        unused_import_keep
    )
}


def get_tweakers() -> Tweakers:
    return TWEAKERS
