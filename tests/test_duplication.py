import pytest
from edulint.options import Option
from edulint.linters import Linter
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
    ("024329-workdays.py", [
        lazy_problem().set_line(56)
    ]),
    ("024535-credit.py", [
        lazy_problem().set_line(23)
        .set_text("Identical code inside all if's branches, move 3 lines after the if."),
        # lazy_problem().set_line(35),
    ]),
    ("052786-course.py", []),
    ("054050-course.py", [
        lazy_problem().set_line(31)
    ]),
    ("074168-doubly_linked.py", [
        lazy_problem().set_line(31)  # dubious
    ]),
    ("074242-tortoise.py", [
        lazy_problem().set_line(32),
        lazy_problem().set_line(32),
        lazy_problem().set_line(65),
        lazy_problem().set_line(65)
    ]),
    ("124573-lists.py", [
        # lazy_problem().set_line(51)
        # .set_text("Identical code inside all if's branches, move 1 lines after the if.")
    ]),
    ("hw21739.py", [  # TODO more precise detection
        lazy_problem().set_line(40)
        .set_text("Identical code inside all if's branches, move 9 lines after the if."),
        lazy_problem().set_line(42)
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
    ("uc_92_9765_21_23.py", [lazy_problem().set_code("R6851").set_line(2)]),
])
def test_identical_before_after_branch(filename: str, expected_output: List[Problem]) -> None:
    apply_and_lint(
        filename,
        [Arg(Option.PYLINT, "--enable=identical-before-after-branch")],
        expected_output
    )

@pytest.mark.parametrize("filename,expected_output", [
    ("uc_88_6816_15_15.py", [lazy_problem().set_line(5)]),
])
def test_identical_if_branches(filename: str, expected_output: List[Problem]) -> None:
    apply_and_lint(
        filename,
        [Arg(Option.PYLINT, "--enable=identical-if-branches")],
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
    ("0ba2fdc810-p6_cellular.py", []),  # not good advice
    ("730a1a0d05-p6_workdays.py", []),  # not good advice
    ("7e1dd5c338-p2_tortoise.py", []),
    ("c69c0646b0-p4_triangle.py", []),
    ("d8b80cabe6-p6_workdays.py", []),  # is in if
    ("fdc1570861-p6_workdays.py", []),  # is in if
    ("hw34406.py", []),  # is in if
    ("uc_4_2117_13_17.py", []),
])
def test_similar_to_function(filename: str, expected_output: List[Problem]) -> None:
    apply_and_lint(
        filename,
        [Arg(Option.PYLINT, "--enable=similar-to-function")],
        expected_output
    )

@pytest.mark.parametrize("filename,expected_output", [
    ("7e1dd5c338-p2_tortoise.py", []),
    ("c69c0646b0-p4_triangle.py", []),
    ("fdc1570861-p6_workdays.py", [lazy_problem().set_line(47)]),
    ("hw34406.py", []),
    ("uc_4_2117_13_17.py", []),
])
def test_similar_to_function_in_if(filename: str, expected_output: List[Problem]) -> None:
    apply_and_lint(
        filename,
        [Arg(Option.PYLINT, "--enable=similar-to-function-in-if")],
        expected_output
    )

@pytest.mark.parametrize("filename,expected_output", [
    ("0642a5c1d7-hw4.py", []),  # dubious
    ("117cb0510a-midterm.py", [lazy_problem().set_line(6).set_end_line(17)]),
    ("1687aeed39-hw4.py", []),
    ("7e1dd5c338-p2_tortoise.py", []),
    ("b3b13aa3f7-p5_merge.py", [lazy_problem().set_line(37)]),
    ("uc_10_7828_23_16.py", []),
    ("uc_4_0123_22_08.py", [lazy_problem().set_line(4).set_end_line(7)]),
    ("uc_52_2125_16_10.py", []),
    ("uc_94_2813_13_57.py", [lazy_problem().set_line(6).set_end_line(11)]),
    ("ut_57_4473_30_10.py", [lazy_problem().set_line(2)]),
    ("ut_57_5508_21_10.py", [lazy_problem().set_line(1)]),
    ("ut_57_9336_15_20.py", [lazy_problem().set_line(1)]),
    ("ut_80_2230_13_11.py", []),
    ("ut_80_3906_24_11.py", [lazy_problem().set_source(Linter.PYLINT)]),  # report only one missing loop, others are misshapen
    ("ut_80_8916_12_20.py", [lazy_problem().set_source(Linter.PYLINT)]),
    ("ut_98_8463_20_35.py", [lazy_problem().set_source(Linter.PYLINT)]),
    ("voter_pennant_twirl_mayday.py", [lazy_problem().set_line(36)]),
])
def test_similar_to_loop(filename: str, expected_output: List[Problem]) -> None:
    apply_and_lint(
        filename,
        [Arg(Option.PYLINT, "--enable=similar-to-loop")],
        expected_output
    )

@pytest.mark.parametrize("lines,expected_output", [
    ([  # 0
        "f(0)",
        "f(1)",
        "f(2)",
        "f(3)",
        "f(4)",
    ], [lazy_problem().set_line(1)]),
    ([  # 1
        "f(v + 0)",
        "f(v + 1)",
        "f(v + 2)",
        "f(v + 3)",
        "f(v + 4)",
    ], [lazy_problem().set_line(1)]),
    ([  # 2
        "f(v)",
        "f(v + 1)",
        "f(v + 2)",
        "f(v + 3)",
        "f(v + 4)",
    ], [lazy_problem().set_line(1)]),
    ([  # 3
        "f(v)",
        "f(v * 2)",
        "f(v * 3)",
        "f(v * 4)",
        "f(v * 5)",
    ], [lazy_problem().set_line(1)]),
    ([  # 4
        "f(0)",
        "f(v)",
        "f(v * 2)",
        "f(v * 3)",
        "f(v * 4)",
    ], [lazy_problem().set_line(1)]),
    ([  # 5
        "f(5)",
        "f(5 + v)",
        "f(5 + v * 2)",
        "f(5 + v * 3)",
        "f(5 + v * 4)",
    ], [lazy_problem().set_line(1)]),
    ([  # 6
        "f(k)",
        "f(k + v)",
        "f(k + v * 2)",
        "f(k + v * 3)",
        "f(k + v * 4)",
    ], [lazy_problem().set_line(1)]),
    ([  # 7
        "f(0)",
        "f(v * 2)",
        "f(v * 3)",
        "f(v * 4)",
        "f(v * 5)",
    ], [lazy_problem().set_line(2)]),
])
def test_similar_to_loop_custom(lines: List[str], expected_output: List[Problem]) -> None:
    create_apply_and_lint(
        lines,
        [Arg(Option.PYLINT, "--enable=similar-to-loop")],
        expected_output
    )

@pytest.mark.parametrize("lines,expected_output", [
    ([  # 0
        "def fun(c1, c2):",
        "    if c1:",
        "        if c2:",
        "            print('hello')",
        "            print('kind')",
        "        else:",
        "            print('cruel')",
        "            print('world')",
        "    else:",
        "        if c2:",
        "            print('cruel')",
        "            print('world')",
        "        else:",
        "            print('hello')",
        "            print('kind')",

    ], [lazy_problem().set_line(2)]),
])
def test_twisted_to_restructured(lines: List[str], expected_output: List[Problem]) -> None:
    create_apply_and_lint(
        lines,
        [Arg(Option.PYLINT, "--enable=twisted-if-to-restructured")],
        expected_output
    )

@pytest.mark.parametrize("lines,expected_output", [
    ([  # 0
        "def fun(c1, c2):",
        "    if c1:",
        "        if c2:",
        "            print('hello')",
        "            print('kind')",
        "        else:",
        "            print('cruel')",
        "            print('world')",
        "    else:",
        "        if c2:",
        "            print('hello')",
        "            print('foo')",
        "        else:",
        "            print('cruel')",
        "            print('world')",

    ], [lazy_problem().set_line(2)]),
])
def test_nested_to_restructured_custom(lines: List[str], expected_output: List[Problem]) -> None:
    create_apply_and_lint(
        lines,
        [Arg(Option.PYLINT, "--enable=nested-if-to-restructured")],
        expected_output
    )

@pytest.mark.parametrize("filename,expected_output", [
    ("uc_28_6710_05_14.py", []),
])
def test_nested_to_restructured(filename: str, expected_output: List[Problem]) -> None:
    apply_and_lint(
        filename,
        [Arg(Option.PYLINT, "--enable=nested-if-to-restructured")],
        expected_output
    )

@pytest.mark.parametrize("filename,expected_output", [
    ("ut_80_2861_19_63.py", [lazy_problem().set_line(3).set_end_line(10)]),
])
def test_similar_to_loop_merge(filename: str, expected_output: List[Problem]) -> None:
    apply_and_lint(
        filename,
        [Arg(Option.PYLINT, "--enable=similar-to-loop-merge")],
        expected_output
    )

@pytest.mark.parametrize("filename,expected_output", [
    ("051746-gps.py", [lazy_problem().set_line(71)]),
    ("ut_80_0402_13_19.py", [
        lazy_problem().set_line(8).set_end_line(10),
        # remaining are also true, but currently overriden by loop suggestion
        # lazy_problem().set_line(12),
        # lazy_problem().set_line(16),
        # lazy_problem().set_line(20),
        # lazy_problem().set_line(24),
        # lazy_problem().set_line(28),
    ]),
    ("ut_92_5508_03_10.py", [lazy_problem().set_line(7)]),
])
def test_similar_to_call(filename: str, expected_output: List[Problem]) -> None:
    apply_and_lint(
        filename,
        [Arg(Option.PYLINT, "--enable=similar-to-call")],
        expected_output
    )


# TODO later, currently too ambitions but probably too rare
# @pytest.mark.parametrize("lines,expected_output", [
#     ([  # 0
#         "def fun(x):",
#         "    a(x)",
#         "    b(x)",
#         "x = 5",
#         "a(x)",
#         "b(x)"
#     ], [lazy_problem().set_line(5)]),
#     ([  # 1
#         "def fun(x):",
#         "    a(x)",
#         "    b(x)",
#         "a(5)",
#         "b(5)"
#     ], [lazy_problem().set_line(4)]),
#     ([  # 2
#         "def fun(x):",
#         "    a(x)",
#         "    b(x)",
#         "lst = []",
#         "a(lst[0])",
#         "b(lst[0])"
#     ], [lazy_problem().set_line(5)]),
#     ([  # 3
#         "def fun(x):",
#         "    a(x)",
#         "    b(x)",
#         "lst = []",
#         "a(lst[0])",
#         "b(lst[1])"
#     ], []),
#     ([  # 4
#         "def fun(x):",
#         "    y = a(x)",
#         "    z = b(y)",
#         "    return z"
#         "p = a(5)",
#         "q = b(p)",
#         "print(q)"
#     ], [lazy_problem().set_line(5)]),
#     ([  # 5
#         "def fun(x):",
#         "    y = a(x)",
#         "    z = b(y)",
#         "    return int(z)"
#         "p = a(5)",
#         "q = b(p)",
#         "print(int(q))"
#     ], [lazy_problem().set_line(5)]),
#     ([  # 6
#         "def fun(x):",
#         "    y = a(x)",
#         "    z = b(y)",
#         "    return int(z) + 1"
#         "p = a(5)",
#         "q = b(p)",
#         "print(int(q))"
#     ], []),
#     ([  # 7
#         "def fun(x):",
#         "    y = a(x)",
#         "    z = b(y)",
#         "    return z",
#         "x = 5",
#         "y = a(x)",
#         "z = b(y)",
#         "print(z)"
#     ], [lazy_problem().set_line(6)]),
# ])
# def test_similar_to_call_custom(lines: List[str], expected_output: List[Problem]) -> None:
#     create_apply_and_lint(
#         lines,
#         [Arg(Option.PYLINT, "--enable=similar-to-call")],
#         expected_output
#     )

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
    ("uc_73_2551_11_17.py", [lazy_problem().set_line(3), lazy_problem().set_line(5)]),
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
    ("uc_73_3819_50_56.py", [lazy_problem().set_line(3)]), # multi-step
    ("uc_73_3819-20_56.py", [lazy_problem().set_line(3), lazy_problem().set_line(7)]),
    ("uc_73_3897_10_43.py", [lazy_problem().set_line(3)]), # multi-step
    ("uc_73_5468_12_52.py", []),
    ("uc_73_7863_14_44.py", [lazy_problem().set_line(3)]), # multi-step
    ("uc_73_8593_19_21.py", []),
])
def test_if_into_block(filename: str, expected_output: List[Problem]) -> None:
    apply_and_lint(
        filename,
        [Arg(Option.PYLINT, "--enable=if-into-block,twisted-if-to-restructured,nested-if-to-restructured")],
        expected_output
    )


@pytest.mark.parametrize("filename,expected_output", [
    ("0379f32d24-p6_workdays.py", [lazy_problem().set_code("R6802").set_line(75)])
])
def test_interactions(filename: str, expected_output: List[Problem]) -> None:
    apply_and_lint(
        filename,
        [Arg(Option.PYLINT, "--enable=big-no-duplicate-code")],
        expected_output
    )