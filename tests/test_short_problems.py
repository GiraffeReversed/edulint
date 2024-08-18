import pytest
from edulint.options import Option
from edulint.config.arg import Arg
from edulint.linting.problem import Problem
from utils import lazy_problem, apply_and_lint, create_apply_and_lint
from typing import List


class TestShort:
    @pytest.mark.parametrize("lines,expected_output", [
        ([
            "def fun(x, y):",
            "    if x > y:",
            "        print('foo')",
            "    elif x <= y:",
            "        print('bar')"
        ], [
            lazy_problem().set_line(4).set_code("R6611")
        ]),
        ([
            "def fun(x, y):",
            "    if x > y:",
            "        print('foo')",
            "    if x <= y:",
            "        print('bar')"
        ], [
            # lazy_problem().set_line(3).set_code("R6611")  # TODO report another defect
        ]),
        ([
            "def fun(x, y):",
            "    if x > y:",
            "        print('foo')",
            "    if x <= y:",
            "        print('bar')",
            "    else:",
            "        print('foobar')"
        ], [
        ]),
    ])
    def test_short_custom(self, lines: List[str], expected_output: List[Problem]) -> None:
        create_apply_and_lint(
            lines,
            [Arg(Option.PYLINT, "--enable=short-problems")],
            expected_output
        )

    @pytest.mark.parametrize("lines,expected_output", [
        ([
            "def foo(a):",
            "    a = a + 1",
        ], [lazy_problem()]),
        # ([
        #     "def foo(a):",
        #     "    a = a * 2",
        # ], []),
        ([
            "def foo(a):",
            "    a = a + [0]",
        ], []),
        ([
            "def foo(a, b):",
            "    a = a + b",
        ], []),
        ([
            "def foo(a):",
            "    a = [0] + a",
        ], []),
        ([
            "def foo(a):",
            "    a = a + 'a'",
        ], [lazy_problem()]),
        ([
            "def foo(a):",
            "    a = 'a' + a",
        ], []),
        ([
            "def foo(a):",
            "    a = a & 2",
        ], [lazy_problem()]),
        ([
            "def foo(a):",
            "    a = a & {'a'}",
        ], []),
        ([
            "def foo(a, b):",
            "    a = a & b",
        ], []),
    ])
    def test_augassign_custom(self, lines: List[str], expected_output: List[Problem]) -> None:
        create_apply_and_lint(
            lines,
            [Arg(Option.PYLINT, "--enable=use-augmented-assign")],
            [problem.set_code("R6609") for problem in expected_output]
        )

    @pytest.mark.parametrize("lines,expected_output", [
        (["1 is True"], [lazy_problem()]),
        (["1 is not True"], [lazy_problem()]),
        (["1 is None"], []),
        (["1 is not None"], []),
    ])
    def test_no_is_custom(self, lines: List[str], expected_output: List[Problem]) -> None:
        create_apply_and_lint(
            lines,
            [Arg(Option.PYLINT, "--enable=no-is-bool")],
            [problem.set_code("R6613") for problem in expected_output]
        )

    @pytest.mark.parametrize("filename,expected_output", [
        ("044050-vigenere.py", [
            lazy_problem().set_code("R6614").set_line(38)
            .set_text("Use \"ord('A')\" instead of using the magical constant 65."),
            lazy_problem().set_code("R6615").set_line(39)
            .set_text("Remove the call to 'ord' and compare to the string directly \"> 'Z'\" instead of using "
                      "the magical constant 91. Careful, this may require changing the comparison operator."),
            lazy_problem().set_code("R6614").set_line(40)
            .set_text("Use \"(ord('Z') + 1)\" instead of using the magical constant 91."),
            lazy_problem().set_code("R6614").set_line(68)
            .set_text("Use \"ord('A')\" instead of using the magical constant 65."),
            lazy_problem().set_code("R6615").set_line(69)
            .set_text("Remove the call to 'ord' and compare to the string directly \"< 'A'\" instead of using "
                      "the magical constant 65. Careful, this may require changing the comparison operator."),
            lazy_problem().set_code("R6614").set_line(70)
            .set_text("Use \"ord('A')\" instead of using the magical constant 65.")
        ]),
        ("044262-vigenere.py", [  # TODO detect also 42 and 72
            lazy_problem().set_code("R6615").set_line(36)
            .set_text("Remove the call to 'ord' and compare to the string directly \"< 'A'\" instead of using "
                      "the magical constant 65. Careful, this may require changing the comparison operator."),
            lazy_problem().set_code("R6615").set_line(36)
            .set_text("Remove the call to 'ord' and compare to the string directly \"> '['\" instead of using "
                      "the magical constant 91. Careful, this may require changing the comparison operator."),
            lazy_problem().set_code("R6615").set_line(66),
            lazy_problem().set_code("R6615").set_line(66)
            .set_text("Remove the call to 'ord' and compare to the string directly \"> '['\" instead of using "
                      "the magical constant 91. Careful, this may require changing the comparison operator."),
        ]),
        ("048426-ipv4.py", [
            lazy_problem().set_code("R6614").set_line(4)
            .set_text("Use \"ord('0')\" instead of using the magical constant 48.")
        ]),
        ("hw34017.py", [
            lazy_problem().set_code("R6615").set_line(177),
            lazy_problem().set_code("R6615").set_line(177)
            .set_text("Remove the call to 'ord' and compare to the string directly \"< 'D'\" instead of using "
                      "the magical constant 68. Careful, this may require changing the comparison operator."),
            lazy_problem().set_code("R6615").set_line(177),
            lazy_problem().set_code("R6615").set_line(177)
            .set_text("Remove the call to 'ord' and compare to the string directly \"< '3'\" instead of using "
                      "the magical constant 51. Careful, this may require changing the comparison operator."),
            lazy_problem().set_code("R6614").set_line(178),
        ]),
    ])
    def test_ord_files(self, filename: str, expected_output: List[Problem]) -> None:
        apply_and_lint(
            filename,
            [
                Arg(Option.PYLINT, "--enable=use-ord-letter,use-literal-letter")
            ],
            expected_output
        )

    @pytest.mark.parametrize("filename,expected_output", [
        ("010666-prime.py", [
            lazy_problem().set_code("R6604").set_line(12).set_text("Do not use while loop with else."),
            lazy_problem().set_code("R6609").set_line(15).set_text("Use augmented assignment: 'i += 1'"),
        ]),
        ("012889-pythagorean.py", [
            lazy_problem().set_code("R6602").set_line(23).set_text("Use integral division //."),
            lazy_problem().set_code("R6602").set_line(24),
            lazy_problem().set_code("R6602").set_line(25),
        ]),
        ("014290-coins.py", [
            lazy_problem().set_code("R6608").set_line(27).set_text("Redundant arithmetic: 1 * (value // 1)")
        ]),
        ("014494-next.py", [
            lazy_problem().set_code("R6602").set_line(5).set_text("Use integral division //."),
            lazy_problem().set_code("R6608").set_line(16).set_text("Redundant arithmetic: number**1"),
        ]),
        ("014661-p5_fibsum.py", [
            lazy_problem().set_code("R6609").set_line(15),
            lazy_problem().set_code("R6609").set_line(18),
            lazy_problem().set_code("R6609").set_line(19),
            lazy_problem().set_code("R6609").set_line(20),
            lazy_problem().set_code("R6611").set_line(23).set_text("Use else instead of elif."),
            lazy_problem().set_code("R6609").set_line(24),

        ]),
        ("017667-prime.py", [
            lazy_problem().set_code("R6616").set_line(5).set_text("Use early return."),
            lazy_problem().set_code("R6604").set_line(6).set_text("Do not use for loop with else."),
        ]),
        ("022859-digit_sum.py", [
            lazy_problem().set_code("R6601").set_line(20)
            .set_text("Use lst.append(number % 7) instead of lst += [number % 7].")
        ]),
        ("024042-cards.py", [
            lazy_problem().set_code("R6609").set_line(9).set_text("Use augmented assignment: 'number //= 10'"),
            lazy_problem().set_code("R6613").set_line(37)
            .set_text("Use 'is_valid_card(number)' directly rather than as 'is_valid_card(number) is True'."),
            lazy_problem().set_code("R6613").set_line(55),
        ]),
        ("024180-delete.py", [
            lazy_problem().set_code("R6606").set_line(7)
            .set_text("The for loop makes only one iteration.")
        ]),
        ("024233-cards.py", [
            lazy_problem().set_code("R6608").set_line(22).set_text("Redundant arithmetic: 0 + number"),
            lazy_problem().set_code("R6616").set_line(23),
            lazy_problem().set_code("R6608").set_line(42).set_text("Redundant arithmetic: 0 + number"),
            lazy_problem().set_code("R6616").set_line(43),
            lazy_problem().set_code("R6616").set_line(47)
        ]),
        ("024371-cards.py", [
            lazy_problem().set_code("R6606").set_line(12).set_text("The for loop makes no iterations.")
        ]),
        ("024371-workdays.py", [
            lazy_problem().set_code("R6606").set_line(29)
            .set_text("The for loop makes only one iteration."),
            lazy_problem().set_code("R6608").set_line(30).set_text("Redundant arithmetic: i + 0"),
        ]),
        ("024491-cards.py", [
            lazy_problem().set_code("R6606").set_line(86)
            .set_text("The for loop makes only one iteration.")
        ]),
        ("024657-bisection.py", [
            lazy_problem().set_code("R6608").set_line(6).set_text("Redundant arithmetic: 0 - eps"),
            lazy_problem().set_code("R6608").set_line(6).set_text("Redundant arithmetic: 0 + eps"),
            lazy_problem().set_code("R6608").set_line(8).set_text("Redundant arithmetic: 0 - eps"),
            lazy_problem().set_code("R6608").set_line(10).set_text("Redundant arithmetic: 0 + eps"),
            lazy_problem().set_code("R6608").set_line(12).set_text("Redundant arithmetic: 0 + eps"),
            lazy_problem().set_code("R6608").set_line(14).set_text("Redundant arithmetic: 0 + eps"),
        ]),
        ("032630-concat.py", [
            lazy_problem().set_code("R6608").set_line(5).set_text("Redundant arithmetic: [0] * 0")
        ]),
        ("041630-ipv4.py", [
            lazy_problem().set_code("R6603").set_line(15).set_text("Use isdecimal to test if string contains a number.")
        ]),
        ("043232-person_id.py", [  # no use else instead of elif on line
            lazy_problem().set_code("R6613").set_line(44),
            lazy_problem().set_code("R6613").set_line(44),
        ]),
        ("044834-ipv4.py", [
            lazy_problem().set_code("R6603").set_line(15).set_text("Use isdecimal to test if string contains a number.")
        ]),
        ("064633-p4_histogram.py", [
            lazy_problem().set_code("R6611").set_line(35).set_text("Use else instead of elif.")
        ]),
        ("085286-p1_count.py", [
            lazy_problem().set_code("R6611").set_line(27).set_text("Use else instead of elif."),
            lazy_problem().set_code("R6612").set_line(30).set_text("Unreachable else."),
            lazy_problem().set_code("R6611").set_line(41).set_text("Use else instead of elif."),
            lazy_problem().set_code("R6612").set_line(44).set_text("Unreachable else."),
        ]),
        ("104174-ipv4_restore.py", [
            lazy_problem().set_code("R6610").set_line(38).set_text("Do not multiply list with mutable content.")
        ]),
        ("104584-p4_digits.py", []),
        ("hw14358.py", [
            lazy_problem().set_code("R6609").set_line(31).set_text("Use augmented assignment: 'b += 1'"),
            lazy_problem().set_code("R6609").set_line(34).set_text("Use augmented assignment: 'a += 1'"),
            lazy_problem().set_code("R6608").set_line(44).set_text("Redundant arithmetic: num // num"),
            lazy_problem().set_code("R6609").set_line(50).set_text("Use augmented assignment: 'count += 1'"),
            lazy_problem().set_code("R6609").set_line(51).set_text("Use augmented assignment: 'number //= n'"),
            lazy_problem().set_code("R6609").set_line(53).set_text("Use augmented assignment: 'primes += 1'"),
            lazy_problem().set_code("R6609").set_line(54),
            lazy_problem().set_code("R6609").set_line(56),
            lazy_problem().set_code("R6609").set_line(57),
        ]),
        ("hw34328.py", [
            lazy_problem().set_code("R6608").set_line(79).set_text("Redundant arithmetic: '' + str(count)")
        ]),
        ("hw34451.py", [
            lazy_problem().set_code("R6616").set_line(13),
            lazy_problem().set_code("R6607").set_line(44)
            .set_text("Use exponentiation instead of repeated muliplication in i * i * i."),
            lazy_problem().set_code("R6607").set_line(47)
            .set_text("Use exponentiation instead of repeated muliplication in i * i * i."),
            lazy_problem().set_code("R6607").set_line(63)
            .set_text("Use exponentiation instead of repeated muliplication in i * i * i."),
            lazy_problem().set_code("R6607").set_line(66)
            .set_text("Use exponentiation instead of repeated muliplication in i * i * i."),
            lazy_problem().set_code("R6613").set_line(98)
            .set_text("Use 'not end' directly rather than as 'end is False'.")
        ]),
        ("hw35219.py", [
            lazy_problem().set_code("R6601").set_line(34)
            .set_text("Use coords_cw.append((-y, x)) instead of coords_cw += [(-y, x)]."),
            lazy_problem().set_code("R6601").set_line(41)
            .set_text("Use coords_ccw.append((y, -x)) instead of coords_ccw += [(y, -x)]."),
            lazy_problem().set_code("R6610").set_line(46).set_text("Do not multiply list with mutable content.")
        ]),
        ("hw45208.py", [
            lazy_problem().set_code("R6605").set_line(32),
            lazy_problem().set_code("R6611").set_line(45),
        ]),
        ("m2630.py", [
            lazy_problem().set_code("R6608").set_line(59).set_text("Redundant arithmetic: [0] * 0"),
            lazy_problem().set_code("R6608").set_line(79).set_text("Redundant arithmetic: num //= num"),
            lazy_problem().set_code("R6608").set_line(83).set_text("Redundant arithmetic: num //= num"),
            lazy_problem().set_code("R6608").set_line(86).set_text("Redundant arithmetic: num //= num"),
            lazy_problem().set_code("R6608").set_line(97).set_text("Redundant arithmetic: position * 1"),
            lazy_problem().set_code("R6613").set_line(144),
            lazy_problem().set_code("R6613").set_line(144),
        ]),
        ("m2650.py", [
            lazy_problem().set_code("R6609").set_line(11),
            lazy_problem().set_code("R6609").set_line(41),
            lazy_problem().set_code("R6609").set_line(44),
            lazy_problem().set_code("R6605").set_line(84).set_text("Use elif."),
        ]),
        ("m5435.py", [
            lazy_problem().set_code("R6609").set_line(7),
            lazy_problem().set_code("R6605").set_line(9).set_text("Use elif."),
            lazy_problem().set_code("R6608").set_line(53).set_text("Redundant arithmetic: valid += 0"),
            lazy_problem().set_code("R6608").set_line(64).set_text("Redundant arithmetic: valid += 0"),
        ]),
        ("ut_157_0762_16_47.py", []),
    ])
    def test_short_files(self, filename: str, expected_output: List[Problem]) -> None:
        apply_and_lint(
            filename,
            [Arg(Option.PYLINT, "--enable=short-problems")],
            expected_output
        )

TEST_FILE_FOR_SIMPLIFICATION_OF_BOOLOP = [
        "def func(l):",
        "    l.append(5)",
        "    return min(l)",
        "def my_function(x, my_list):",
        "    my_list.append(2)",
        "    return x - 1",
        "def func2():",
        "    x = 42",
        "    y = [-5.25, 2.3, 3, 4]",
        "    z = 3.14",
        "    a = x > 2 or x < -2",
        "    b = x >= 2 or x < -2",
        "    c = x >= 2 or x <= -2",
        "    d = x >= -2 or x <= 2",
        "    e = x > 0 or x < 0",
        "    f = x >= 1 or x > 1",
        "    g = x < -3.5 or x > 3.5",
        "    h = x <= 7.59 or x >= -7.59",
        "    i = -0.96 > sum(y) or sum(y) > 0.96",
        "    j = -0.96 > sum(y) or 0.96 < sum(y)",
        "    k = sum(y) > 2 or x > 4",
        "    variable = x <= 2 and x < -5",
        "    m = x < 2 and x <= -5",
        "    n = sum(y) <= 5 and -5 <= sum(y)",
        "    o = abs(min(y)) > -4.47 and abs(min(y)) < 4.47",
        "    l = abs(min(x)) > -3 and abs(min(y)) > 3",
        "    p = float(abs(x + z)) > -8.56 and float(abs(x + z)) < 8.56",
        "    q = x + 1 < -9 or x + 1 > 9",
        "    r = float(abs(sum(reversed(sorted(y))))) < 5 and -5 < float(abs(sum(reversed(sorted(y)))))",
        "    s = my_function(x, y) > 5 and my_function(x, y) < -5",
        "    t = float(sum(map(abs, y))) < 5 and -5 < float(sum(map(abs, y)))",
        "    u = float(sum(y)) >= 5.01 and float(sum(y)) > 5",
        "    v = x > 5 or x > 4 or x > 3 or x < -5 or x <= -7 or x <= -3",
        "    w = x > 5 or x > 4 or x <= -7 or x >= 3 or x < -5 or x <= -3",
        "    aa = x > 5 or x > 4 or x > 3 or x < -5 or x <= -7 or x > -3",
        "    bb = x > 5 or x > 4 or x > 3 or x < -5 or x <= -7 or x > -5",
        "    cc = x < 7 and x < 8 and x > 13",
        "    dd = [[2, 3, 4, -1, -8, 2, -3], [7, 3, 6, 5, 4], [-9, 2]]",
        "    ee = max(map(min, dd)) <= 7 and -9 < max(map(min, dd)) and max(map(min, dd)) < 14.2 and -7 <= max(map(min, dd))",
        "    ff = max(map(min, dd)) < 7 and -9 < max(map(min, dd)) and max(map(min, dd)) < 14.2 and -7 <= max(map(min, dd))",
        "    gg = max(map(func, dd)) <= 7 and -9 < max(map(func, dd)) and max(map(func, dd)) < 14.2 and -7 <= max(map(func, dd))",
        "    hh = -0.5 <= len(y) and len(y) < 5 and x < -5 and 7 < len(y) and len(y) > -5 and x > 5 and -7 <= x or x > 7 or x < -7",
        "    ii = (x + len(y) < 5 and x + len(y) > -5) or (x + len(y) > 4 or x + len(y) < -4)",
        "    jj = max(map(func, dd)) <= 9 and -9 <= max(map(func, dd)) and -9 <= max(map(func, dd))",
    ]

@pytest.mark.parametrize("lines,expected_output", [
    ([
        "x = 7.8",
        "y = [-5.25, 2.3, 3, 4]",
        "z = -20",
        "a = abs(min(y)) > -4.47 and abs(min(y)) < 4.47",
        "c = int(z + abs(sum(reversed(sorted(y))))) < 8.56 and -8.56 < int(z + abs(sum(reversed(sorted(y)))))",
        "d = x + len(y) < 5 and x < 5 and x + len(y) > -10 and x > -5 and x + len(y) > -5",
    ], [
        lazy_problem().set_line(4).set_code("R6617")
        .set_text("'abs(min(y)) > -4.47 and abs(min(y)) < 4.47' can be replaced with 'abs(min(y)) < 4.47'"),
        lazy_problem().set_line(5).set_code("R6617")
        .set_text("'int(z + abs(sum(reversed(sorted(y))))) < 8.56 and int(z + abs(sum(reversed(sorted(y))))) > -8.56' can be replaced with 'abs(int(z + abs(sum(reversed(sorted(y)))))) < 8.56'"),
        lazy_problem().set_line(6).set_code("R6617")
        .set_text("'x + len(y) < 5 and x + len(y) > -10 and x + len(y) > -5' can be replaced with 'abs(x + len(y)) < 5'"),
        lazy_problem().set_line(6).set_code("R6617")
        .set_text("'x < 5 and x > -5' can be replaced with 'abs(x) < 5'"),
    ]),
])
def test_simplification_of_and(lines: List[str], expected_output: List[Problem]) -> None:
    create_apply_and_lint(
        lines,
        [Arg(Option.PYLINT, "--enable=simplifiable-and-with-abs")],
        expected_output
    )

@pytest.mark.parametrize("lines,expected_output", [
    ([
        "x = 7.8",
        "y = [-5.25, 2.3, 3, 4]",
        "a = x >= 2 or x <= -2",
        "b = x + len(y) > 4 or x + len(y) < -4",
        "c = x + 1 < -9 or 9 < x + 1",
        "d = x > 5 or x > 4 or x <= -7 or x >= 3 or x < -5 or x <= -3",
        "e = -0.5 <= len(y) and len(y) < 5 and -7 <= x or x > 7 or x < -7",
        "f = y[0] >= 5 or y[0] <= -5",
    ], [
        lazy_problem().set_line(3).set_code("R6618")
        .set_text("'x >= 2 or x <= -2' can be replaced with 'abs(x) >= 2'"),
        lazy_problem().set_line(4).set_code("R6618")
        .set_text("'x + len(y) > 4 or x + len(y) < -4' can be replaced with 'abs(x + len(y)) > 4'"),
        lazy_problem().set_line(5).set_code("R6618")
        .set_text("'x + 1 < -9 or x + 1 > 9' can be replaced with 'abs(x + 1) > 9'"),
        lazy_problem().set_line(6).set_code("R6618")
        .set_text("'x > 5 or x > 4 or x <= -7 or x >= 3 or x < -5 or x <= -3' can be replaced with 'abs(x) >= 3'"),
        lazy_problem().set_line(7).set_code("R6618")
        .set_text("'x > 7 or x < -7' can be replaced with 'abs(x) > 7'"),
        lazy_problem().set_line(8).set_code("R6618")
        .set_text("'y[0] >= 5 or y[0] <= -5' can be replaced with 'abs(y[0]) >= 5'"),
    ]),
])
def test_simplification_of_or(lines: List[str], expected_output: List[Problem]) -> None:
    create_apply_and_lint(
        lines,
        [Arg(Option.PYLINT, "--enable=simplifiable-or-with-abs")],
        expected_output
    )

@pytest.mark.parametrize("lines,expected_output", [
    ([
        "x = 7.8",
        "y = [-5.25, 2.3, 3, 4]",
        "a = x > -2 or x <= 6",
        "b = x > 0 or x < 0",
        "c = x >= 1 or x > 1",
        "d = x < 2 and x <= -5",
        "e = -(x - 1) > 5 or - (x- 1) < -5 or -(x-1) >= 4",
        "f = ",
    ], [
        lazy_problem().set_line(3).set_code("R6619")
        .set_text("'x >= -2 or x <= 2' can be replaced with 'True'"),
        lazy_problem().set_line(4).set_code("R6619")
        .set_text("'x > 0 or x < 0' can be replaced with 'x != 0'"),
        lazy_problem().set_line(5).set_code("R6619")
        .set_text("'x >= 1 or x > 1' can be replaced with 'x >= 1'"),
        lazy_problem().set_line(6).set_code("R6619")
        .set_text("'x < 2 and x <= -5' can be replaced with 'x <= -5'"),
        lazy_problem().set_line(7).set_code("R6619")
        .set_text("'-(x - 1) > 5 or -(x - 1) < -5 or -(x - 1) >= 4' can be replaced with '-(x - 1) < -5 or -(x - 1) >= 4'"),
    ]),
])
def test_redundant_compare(lines: List[str], expected_output: List[Problem]) -> None:
    create_apply_and_lint(
        lines,
        [Arg(Option.PYLINT, "--enable=redundant-compare-in-condition")],
        expected_output
    )

@pytest.mark.parametrize("lines,expected_output", [
    ([
        "class Person:",
        "    def __init__(self, name, age):",
        "        self.name = name",
        "        self.age = age",
        "    def this_not_pure(self, something):",
        "        something.append(5)",
        "        return something[0]",
        "def foo():",
        "    person = Person('Albert', 56)",
        "    a = person.age > 5 and person.age > 9",
        "    b = person.this_not_pure(y) > 6 or person.this_not_pure(y) < -6",
    ], [
        lazy_problem().set_line(10).set_code("R6619")
        .set_text("'person.age > 5 and person.age > 9' can be replaced with 'person.age > 9'"),
    ]),
])
def test_redundant_compare(lines: List[str], expected_output: List[Problem]) -> None:
    create_apply_and_lint(
        lines,
        [Arg(Option.PYLINT, "--enable=redundant-compare-in-condition")],
        expected_output
    )
