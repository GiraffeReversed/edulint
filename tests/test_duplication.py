import pytest
from edulint.options import Option
from edulint.config.arg import Arg
from edulint.linting.problem import Problem
from utils import lazy_problem, apply_and_lint, create_apply_and_lint
from typing import List


@pytest.mark.parametrize("filename,expected_output", [
    ("013165-coins.py", [
        lazy_problem().set_line(9)
        .set_text("Identical code inside all if's branches, move 1 lines before the if.")
    ]),
    ("015726-prime.py", [
        lazy_problem().set_line(10)
        .set_text("Identical code inside all if's branches, move 1 lines after the if.")
    ]),
    ("016119-fibsum.py", [
        lazy_problem().set_line(22)
        .set_text("Identical code inside all if's branches, move 3 lines after the if.")
    ]),
    ("024535-credit.py", [
        lazy_problem().set_line(23)
        .set_text("Identical code inside all if's branches, move 3 lines after the if."),
        lazy_problem().set_line(35),
    ]),
    ("hw21739.py", [  # TODO more precise detection
        lazy_problem().set_line(40)
        .set_text("Identical code inside all if's branches, move 9 lines after the if."),
        lazy_problem().set_line(42)
        .set_text("Identical code inside all if's branches, move 1 lines after the if."),
        lazy_problem().set_line(53)
        .set_text("Identical code inside all if's branches, move 1 lines after the if."),
        lazy_problem().set_line(67)
        .set_text("Identical code inside all if's branches, move 1 lines after the if."),
        lazy_problem().set_line(109)
        .set_text("Identical code inside all if's branches, move 16 lines after the if."),
        lazy_problem().set_line(164)
        .set_text("Identical code inside all if's branches, move 2 lines before the if."),
        lazy_problem().set_line(164)
        .set_text("Identical code inside all if's branches, move 3 lines after the if.")
    ])
])
def test_duplicate_if_branches(filename: str, expected_output: List[Problem]) -> None:
    apply_and_lint(
        filename,
        [Arg(Option.PYLINT, "--disable=all"), Arg(Option.PYLINT, "--enable=duplicate-if-branches")],
        expected_output
    )
