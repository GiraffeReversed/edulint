import pytest
from edulint.options import Option
from edulint.config.arg import Arg
from edulint.linting.problem import Problem
from utils import lazy_problem, apply_and_lint
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
    ("024329-workdays.py", [  # TODO improve
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
def test_identical_before_after_branch(filename: str, expected_output: List[Problem]) -> None:
    apply_and_lint(
        filename,
        [Arg(Option.PYLINT, "--enable=identical-before-after-branch")],
        expected_output
    )


@pytest.mark.parametrize("filename,expected_output", [
    ("012889-geometry.py", [
        lazy_problem().set_line(28).set_end_line(33)
        .set_text("Identical code inside 3 consecutive ifs, join their conditions using 'or'.")
    ]),
    ("012889-pythagorean.py", [
        lazy_problem().set_line(26).set_end_line(29)
        .set_text("Identical code inside 2 consecutive ifs, join their conditions using 'or'.")
    ]),
    ("014341-geometry.py", [
        lazy_problem().set_line(9).set_end_line(14)
    ]),
    ("014613-next.py", [
        lazy_problem().set_line(35).set_end_line(40)
    ]),
    ("034440-cellular.py", [
        lazy_problem().set_line(56).set_end_line(61),
        lazy_problem().set_line(62).set_end_line(65)
    ]),
    ("046586-person_id.py", [
        lazy_problem().set_line(40).set_end_line(56)
        .set_text("Identical code inside 7 consecutive ifs, join their conditions using 'or'.")
    ]),
    ("052975-parse_time.py", []),
])
def test_identical_seq_ifs(filename: str, expected_output: List[Problem]) -> None:
    apply_and_lint(
        filename,
        [Arg(Option.PYLINT, "--enable=identical-seq-ifs")],
        expected_output
    )


@pytest.mark.parametrize("filename,expected_output", [
    ("012853-geometry.py", [  # TODO detect this
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
        [Arg(Option.PYLINT, "--enable=duplicate-exprs")],
        expected_output
    )


@pytest.mark.parametrize("filename,expected_output", [
    ("013145-coins.py", [
        lazy_problem().set_line(5).set_end_line(7)
        .set_text("Duplicate blocks starting on lines 5 and 10. Extract the code to a helper function."),
        lazy_problem().set_line(10).set_end_line(12),
        lazy_problem().set_line(15).set_end_line(17),
        lazy_problem().set_line(20).set_end_line(22),
    ]),
    ("024508-cards.py", [
        lazy_problem().set_line(61).set_end_line(66),
    ])
])
def test_duplicate_blocks(filename: str, expected_output: List[Problem]) -> None:
    apply_and_lint(
        filename,
        [Arg(Option.PYLINT, "--enable=duplicate-blocks")],
        expected_output
    )


@pytest.mark.parametrize("filename,expected_output", [
    ("010666-coins.py", [
        lazy_problem().set_line(13).set_end_line(27)
        .set_text("Duplicate sequence of 5 repetitions of 3 lines of code. Use a loop to avoid this."),
    ]),
    ("014212-coins.py", [
        lazy_problem().set_line(8).set_end_line(19)
        .set_text("Duplicate sequence of 6 repetitions of 2 lines of code. Use a loop to avoid this."),
    ]),
    ("051796-gps.py", []),
    ("hw36211.py", []),
    ("ut156_9802_29_10.py", [
        lazy_problem().set_line(7).set_end_line(14)
        .set_text("Duplicate sequence of 4 repetitions of 2 lines of code. Use a loop to avoid this."),
        lazy_problem().set_line(15).set_end_line(24),
        lazy_problem().set_line(25).set_end_line(36),
        lazy_problem().set_line(37).set_end_line(48),
    ]),
])
def test_duplicate_sequence(filename: str, expected_output: List[Problem]) -> None:
    apply_and_lint(
        filename,
        [Arg(Option.PYLINT, "--enable=duplicate-sequence")],
        expected_output
    )


@pytest.mark.parametrize("filename,expected_output", [
    ("c69c0646b0-p4_triangle.py", [])
])
def test_similar_to_function(filename: str, expected_output: List[Problem]) -> None:
    apply_and_lint(
        filename,
        [Arg(Option.PYLINT, "--enable=similar-to-function")],
        expected_output
    )

@pytest.mark.parametrize("filename,expected_output", [
    ("uc_4_0123_22_08.py", [lazy_problem().set_line(4).set_end_line(7)]),
    ("uc_94_2813_13_57.py", [lazy_problem().set_line(6).set_end_line(11)]),
])
def test_similar_to_loop(filename: str, expected_output: List[Problem]) -> None:
    apply_and_lint(
        filename,
        [Arg(Option.PYLINT, "--enable=similar-to-loop")],
        expected_output
    )

@pytest.mark.parametrize("filename,expected_output", [
    ("0bf69cc1a5-p4_geometry.py", []),
    ("163aadb1dd-p4_geometry.py", []),  # dubious
    ("5ce8692f42-p5_fibsum.py", []),
    ("769200244d-p6_workdays.py", [lazy_problem().set_line(66)]),
    ("7e1dd5c338-p1_digit_sum.py", []), # [lazy_problem().set_line(23)]), dubious
    ("7e1dd5c338-p5_credit.py", []),
    ("9668dff756-p6_workdays.py", []),
    ("ccf4a9f103-p6_workdays.py", []),
    ("custom_if_calls_to_variables.py", []),
    ("fd637a2984-p6_workdays.py", []),
    ("fdc1570861-p6_workdays.py", [lazy_problem().set_line(47)]),  # multiple if branches differing in one value
    ("tarot_card_reader.py", []),
    ("uc_73_0198_15_17.py", [lazy_problem().set_line(6)]),
    ("uc_73_2551_11_17.py", [lazy_problem().set_line(3)]),
    ("uc_73_3819_50_56.py", []),
    ("uc_73_3819-20_56.py", []),
    ("uc_73_3897_10_43.py", [lazy_problem().set_line(3)]),
    ("uc_73_5468_12_52.py", [lazy_problem().set_line(3)]),
    ("uc_73_7863_14_44.py", [lazy_problem().set_line(3)]),
    ("uc_73_8593_19_21.py", []),
])
def test_if_into_variables(filename: str, expected_output: List[Problem]) -> None:
    apply_and_lint(
        filename,
        [Arg(Option.PYLINT, "--enable=if-to-variables")],
        expected_output
    )


@pytest.mark.parametrize("filename,expected_output", [
    ("0bf69cc1a5-p4_geometry.py", []),
    ("163aadb1dd-p4_geometry.py", []),
    ("5ce8692f42-p5_fibsum.py", []),
    ("769200244d-p6_workdays.py", [lazy_problem().set_line(66)]),
    ("7e1dd5c338-p1_digit_sum.py", []),
    ("7e1dd5c338-p5_credit.py", []),
    ("9668dff756-p6_workdays.py", []),
    ("ccf4a9f103-p6_workdays.py", [lazy_problem().set_line(80)]),
    ("custom_if_calls_to_variables.py", []),
    ("fd637a2984-p6_workdays.py", []),
    ("fdc1570861-p6_workdays.py", []),
    ("tarot_card_reader.py", []),
    ("uc_73_0198_15_17.py", []),
    ("uc_73_2551_11_17.py", [lazy_problem().set_line(3)]),
    ("uc_73_3819_50_56.py", [lazy_problem().set_line(6), lazy_problem().set_line(16)]),
    ("uc_73_3819-20_56.py", [lazy_problem().set_line(7), lazy_problem().set_line(18)]),
    ("uc_73_3897_10_43.py", [lazy_problem().set_line(3)]),
    ("uc_73_5468_12_52.py", []),
    ("uc_73_7863_14_44.py", []),
    ("uc_73_8593_19_21.py", []),
])
def test_if_to_ternary(filename: str, expected_output: List[Problem]) -> None:
    apply_and_lint(
        filename,
        [Arg(Option.PYLINT, "--enable=if-to-ternary")],
        expected_output
    )


@pytest.mark.parametrize("filename,expected_output", [
    ("0bf69cc1a5-p4_geometry.py", []),
    ("163aadb1dd-p4_geometry.py", []),
    ("5ce8692f42-p5_fibsum.py", []),
    ("769200244d-p6_workdays.py", [lazy_problem().set_line(66)]),
    ("7e1dd5c338-p1_digit_sum.py", []),
    ("7e1dd5c338-p5_credit.py", []),
    ("9668dff756-p6_workdays.py", []),
    ("ccf4a9f103-p6_workdays.py", []),
    ("custom_if_calls_to_variables.py", []),
    ("fd637a2984-p6_workdays.py", []),
    ("fdc1570861-p6_workdays.py", []),
    ("tarot_card_reader.py", []),
    ("uc_73_0198_15_17.py", []),
    ("uc_73_2551_11_17.py", []), # dubious
    ("uc_73_3819_50_56.py", []), # dubious
    ("uc_73_3819-20_56.py", [lazy_problem().set_line(3)]),
    ("uc_73_3897_10_43.py", []), # dubious
    ("uc_73_5468_12_52.py", []),
    ("uc_73_7863_14_44.py", []), # dubious
    ("uc_73_8593_19_21.py", []),
])
def test_if_into_block(filename: str, expected_output: List[Problem]) -> None:
    apply_and_lint(
        filename,
        [Arg(Option.PYLINT, "--enable=if-into-block")],
        expected_output
    )