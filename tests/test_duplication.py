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
        # lazy_problem().set_line(10)
        # .set_text("Identical code inside all if's branches, move 1 lines after the if.")
    ]),
    ("016119-fibsum.py", [
        lazy_problem().set_line(22)
        .set_text("Identical code inside all if's branches, move 3 lines after the if.")
    ]),
    ("023171-credit.py", [
        lazy_problem().set_line(26),
        lazy_problem().set_line(38)
    ]),
    ("024056-cards.py", [
        lazy_problem().set_line(7)
    ]),
    ("024329-workdays.py", [ # TODO improve
        # lazy_problem().set_line(56)
    ]),
    ("024535-credit.py", [
        lazy_problem().set_line(23)
        .set_text("Identical code inside all if's branches, move 3 lines after the if."),
        lazy_problem().set_line(35),
    ]),
    ("052786-course.py", []),
    ("054050-course.py", [
        lazy_problem().set_line(31)
    ]),
    ("074168-doubly_linked.py", []),
    ("074242-tortoise.py", [
        lazy_problem().set_line(32),
        lazy_problem().set_line(32),
        lazy_problem().set_line(65),
        lazy_problem().set_line(65)
    ]),
    ("124573-lists.py", [
        lazy_problem().set_line(51)
        .set_text("Identical code inside all if's branches, move 1 lines after the if.")
    ]),
    ("hw21739.py", [  # TODO more precise detection
        lazy_problem().set_line(40)
        .set_text("Identical code inside all if's branches, move 9 lines after the if."),
        lazy_problem().set_line(42)
        .set_text("Identical code inside all if's branches, move 1 lines after the if."),
        lazy_problem().set_line(53)
        .set_text("Identical code inside all if's branches, move 1 lines after the if."),
        # lazy_problem().set_line(67)
        # .set_text("Identical code inside all if's branches, move 1 lines after the if."),
        # lazy_problem().set_line(87)
        # .set_text("Identical code inside all if's branches, move 2 lines before the if."),
        # lazy_problem().set_line(87)
        # .set_text("Identical code inside all if's branches, move 3 lines after the if."),
        lazy_problem().set_line(109)
        .set_text("Identical code inside all if's branches, move 16 lines after the if."),
        lazy_problem().set_line(164)
        .set_text("Identical code inside all if's branches, move 2 lines before the if."),
        lazy_problem().set_line(164)
        .set_text("Identical code inside all if's branches, move 3 lines after the if.")
    ]),
    ("hw48505.py", []),
])
def test_duplicate_if_branches(filename: str, expected_output: List[Problem]) -> None:
    apply_and_lint(
        filename,
        [Arg(Option.PYLINT, "--disable=all"), Arg(Option.PYLINT, "--enable=duplicate-if-branches")],
        expected_output
    )

@pytest.mark.parametrize("filename,expected_output", [
    ("012889-geometry.py", [
        lazy_problem().set_line(28)
        .set_text("Identical code inside 3 consecutive ifs, join their conditions using 'or'.")
    ]),
    ("012889-pythagorean.py", [
        lazy_problem().set_line(26)
        .set_text("Identical code inside 2 consecutive ifs, join their conditions using 'or'.")
    ]),
    ("014341-geometry.py", [
        lazy_problem().set_line(9)
    ]),
    ("014613-next.py", [
        lazy_problem().set_line(35)
    ]),
    ("034440-cellular.py", [
        lazy_problem().set_line(56),
        lazy_problem().set_line(62)
    ]),
    ("046586-person_id.py", [
        lazy_problem().set_line(40)
        .set_text("Identical code inside 7 consecutive ifs, join their conditions using 'or'.")
    ]),
    ("052975-parse_time.py", []),
])
def test_duplicate_seq_ifs(filename: str, expected_output: List[Problem]) -> None:
    apply_and_lint(
        filename,
        [Arg(Option.PYLINT, "--disable=all"), Arg(Option.PYLINT, "--enable=duplicate-seq-ifs")],
        expected_output
    )


@pytest.mark.parametrize("filename,expected_output", [
    ("012853-geometry.py", [ # TODO detect this
        lazy_problem().set_line(8)
        .set_text("A complex expression 'not (a + b > c and b + c > a and c + a > b)' used repeatedly "
                  "(on lines 8, 18, 27). Extract it to a local variable or create a helper function.")
    ]),
    ("014024-pythagorean.py", [
        lazy_problem().set_line(19)
        .set_text("A complex expression 'sqrt(a**2 + b**2)' used repeatedly (on lines 19, 20). Extract it to a "
                  "local variable or create a helper function."),
        lazy_problem().set_line(21)
        .set_text("A complex expression 'a + b + c > result' used repeatedly (on lines 21, 27, 33). Extract it to a "
        "local variable or create a helper function."),
        lazy_problem().set_line(25),
        lazy_problem().set_line(31),
    ]),
    ("042643-edge_detection.py", [])
])
def test_duplicate_exprs(filename: str, expected_output: List[Problem]) -> None:
    apply_and_lint(
        filename,
        [Arg(Option.PYLINT, "--disable=all"), Arg(Option.PYLINT, "--enable=duplicate-exprs")],
        expected_output
    )
