import pytest
from edulint.options import Option
from edulint.config.arg import Arg
from edulint.linting.problem import Problem
from test_utils import lazy_problem, apply_and_lint, create_apply_and_lint
from typing import List


def _test_simplify_if(lines: List[str], expected_output: List[Problem], code: str) -> None:
    create_apply_and_lint(
        lines,
        [Arg(Option.PYLINT, f"--enable={code}")],
        [p.set_code(code) for p in expected_output]
    )


@pytest.mark.parametrize("lines,expected_output", [
    ([
        "def yyy(x):",
        "    if x:",
        "        return True",
        "    else:",
        "        return False"
    ], [
        lazy_problem().set_line(2)
        .set_text("The if statement can be replaced with 'return x'")
    ]),
    ([
        "def xxx(x):",
        "    if x:",
        "        return False",
        "    else:",
        "        return True"
    ], [
        lazy_problem().set_line(2)
        .set_text("The if statement can be replaced with 'return <negated x>'"),
    ]),
    ([
        "def xxx(x):",
        "    if x:",
        "        return True",
        "    return False"
    ], [
        lazy_problem().set_line(2)
        .set_text("The if statement can be replaced with 'return x'"),
    ]),
    ([
        "def xxx(x):",
        "    if x:",
        "        return False",
        "    return True"
    ], [
        lazy_problem().set_line(2)
        .set_text("The if statement can be replaced with 'return <negated x>'"),
    ]),
])
def test_simplify_if_statement_single_var_custom(lines: List[str], expected_output: List[Problem]) -> None:
    _test_simplify_if(lines, expected_output, "R6201")


@pytest.mark.parametrize("lines,expected_output", [
    ([
        "def xxx(x, y):",
        "    if x:",
        "        return True",
        "    return y"
    ], [
        lazy_problem().set_line(2)
        .set_text("The if statement can be replaced with 'return x or y'")
    ]),
    ([
        "def xxx(x, y):",
        "    if x:",
        "        return False",
        "    return y"
    ], [
        lazy_problem().set_line(2)
        .set_text("The if statement can be replaced with 'return <negated x> and y'")
    ]),
    ([
        "def xxx(x, y):",
        "    if x:",
        "        return y",
        "    return False"
    ], [
        lazy_problem().set_line(2)
        .set_text("The if statement can be replaced with 'return x and y'")
    ]),
    ([
        "def xxx(x, y):",
        "    if x:",
        "        return y",
        "    return True"
    ], [
        lazy_problem().set_line(2)
        .set_text("The if statement can be replaced with 'return <negated x> or y'")
    ]),
    ([
        "def xxx(x, y):",
        "    if x:",
        "        return True",
        "    else:",
        "        return y"
    ], [
        lazy_problem().set_line(2)
        .set_text("The if statement can be replaced with 'return x or y'")
    ]),
    ([
        "def xxx(x, y):",
        "    if x:",
        "        return False",
        "    else:",
        "        return y"
    ], [
        lazy_problem().set_line(2)
        .set_text("The if statement can be replaced with 'return <negated x> and y'")
    ]),
    ([
        "def xxx(x, y):",
        "    if x:",
        "        return y",
        "    else:",
        "        return False"
    ], [
        lazy_problem().set_line(2)
        .set_text("The if statement can be replaced with 'return x and y'")
    ]),
    ([
        "def xxx(x, y):",
        "    if x:",
        "        return y",
        "    else:",
        "        return True"
    ], [
        lazy_problem().set_line(2)
        .set_text("The if statement can be replaced with 'return <negated x> or y'")
    ]),
])
def test_simplify_if_statement_two_vars_custom(lines: List[str], expected_output: List[Problem]) -> None:
    _test_simplify_if(lines, expected_output, "R6202")


@pytest.mark.parametrize("lines,expected_output", [
    ([
        "def xxx(x, y, z):",
        "    if x and z:",
        "        return y",
        "    return False"
    ], [
        lazy_problem().set_line(2)
        .set_text("The if statement can be replaced with 'return x and z and y'")
    ]),
    ([
        "def xxx(x, y, z):",
        "    if x or z:",
        "        return y",
        "    return False"
    ], [
        lazy_problem().set_line(2)
        .set_text("The if statement can be replaced with 'return (x or z) and y'")
    ]),
    ([
        "def xxx(x, y, z):",
        "    if x:",
        "        return y and z",
        "    return False"
    ], [
        lazy_problem().set_line(2)
        .set_text("The if statement can be replaced with 'return x and y and z'")
    ]),
    ([
        "def xxx(x, y, z):",
        "    if x:",
        "        return y or z",
        "    return False"
    ], [
        lazy_problem().set_line(2)
        .set_text("The if statement can be replaced with 'return x and (y or z)'")
    ]),
    ([
        "def xxx(x, y, z):",
        "    if x and z:",
        "        return True",
        "    return y"
    ], [
        lazy_problem().set_line(2)
        .set_text("The if statement can be replaced with 'return (x and z) or y'")
    ]),
    ([
        "def xxx(x, y, z):",
        "    if x and z:",
        "        return False",
        "    return y"
    ], [
        lazy_problem().set_line(2)
        .set_text("The if statement can be replaced with 'return <negated (x and z)> and y'")
    ]),
    ([
        "def xxx(x, y, z):",
        "    if x:",
        "        return False",
        "    return y or z"
    ], [
        lazy_problem().set_line(2)
        .set_text("The if statement can be replaced with 'return <negated x> and (y or z)'")
    ]),
    ([
        "def xxx(x, y, z):",
        "    if x or z:",
        "        return y",
        "    return False"
    ], [
        lazy_problem().set_line(2)
        .set_text("The if statement can be replaced with 'return (x or z) and y'")
    ]),
    ([
        "def xxx(x, y, z):",
        "    if x and z:",
        "        return y",
        "    return True"
    ], [
        lazy_problem().set_line(2)
        .set_text("The if statement can be replaced with 'return <negated (x and z)> or y'")
    ]),
    ([
        "def xxx(x, y, z):",
        "    if x and z:",
        "        return True",
        "    else:",
        "        return y"
    ], [
        lazy_problem().set_line(2)
        .set_text("The if statement can be replaced with 'return (x and z) or y'")
    ]),
    ([
        "def xxx(x, y, z):",
        "    if x or z:",
        "        return True",
        "    else:",
        "        return y"
    ], [
        lazy_problem().set_line(2)
        .set_text("The if statement can be replaced with 'return x or z or y'")
    ]),
    ([
        "def xxx(x, y, z):",
        "    if x:",
        "        return True",
        "    else:",
        "        return y and z"
    ], [
        lazy_problem().set_line(2)
        .set_text("The if statement can be replaced with 'return x or (y and z)'")
    ]),
])
def test_simplify_if_statement_three_vars_custom(lines: List[str], expected_output: List[Problem]) -> None:
    _test_simplify_if(lines, expected_output, "R6202")


@pytest.mark.parametrize("lines,expected_output", [
    ([
        "def xxx(x, y):",
        "    if x:",
        "        if y:",
        "            return 0",
        "    return 1"
    ], [
        lazy_problem().set_line(2)
        .set_text("The if statement can be merged with the nested one to 'if x and y:'")
    ]),
])
def test_simplify_if_statement_nested_custom(lines: List[str], expected_output: List[Problem]) -> None:
    _test_simplify_if(lines, expected_output, "R6207")


@pytest.mark.parametrize("lines,expected_output", [
    ([
        "def xxx(x, y):",
        "    if x:",
        "        return 0",
        "    if y:",
        "        return 0",
        "    return 1"
    ], [
        lazy_problem().set_line(2)
        .set_text("The if statement can be merged with the following one to 'if x or y:'")
    ]),
    ([
        "def xxx(x, y):",
        "    if x:",
        "        return True",
        "    if y:",
        "        return False",
        "    return True"
    ], [
    ]),
    ([
        "def xxx(x, y, z):",
        "    if x and y:",
        "        return True",
        "    if z:",
        "        return True",
        "    return True"
    ], [
    ]),
])
def test_simplify_if_statement_multiconds_custom(lines: List[str], expected_output: List[Problem]) -> None:
    _test_simplify_if(lines, expected_output, "R6208")


@pytest.mark.parametrize("lines,expected_output", [
    ([
        "def is_right(a, b, c):",
        "    if c ** 2 == a ** 2 + b ** 2 or a ** 2 == c ** 2 + b ** 2 or \\",
        "       b ** 2 == a ** 2 + c ** 2:",
        "        triangle_is_righ = True",
        "    else:",
        "        triangle_is_righ = False",
        "    return triangle_is_righ"
    ], [
        lazy_problem().set_line(2)
        .set_text("The conditional assignment can be replaced with 'triangle_is_righ = c**2 == a**2 "
                  "+ b**2 or a**2 == c**2 + b**2 or b**2 == a**2 + c**2'")
    ]),
])
def test_simplify_if_assigning_statement_custom(lines: List[str], expected_output: List[Problem]) -> None:
    _test_simplify_if(lines, expected_output, "R6203")


@pytest.mark.parametrize("lines,expected_output", [
    ([
        "def xxx(x, y):",
        "    if x:",
        "        a = True",
        "    else:",
        "        a = y"
    ], [
        lazy_problem().set_line(2)
        .set_text("The conditional assignment can be replaced with 'a = x or y'")
    ]),
    ([
        "def xxx(x, y):",
        "    if x:",
        "        a = False",
        "    else:",
        "        a = y"
    ], [
        lazy_problem().set_line(2)
        .set_text("The conditional assignment can be replaced with 'a = <negated x> and y'")
    ]),
    ([
        "def xxx(x, y):",
        "    if x:",
        "        a = y",
        "    else:",
        "        a = False"
    ], [
        lazy_problem().set_line(2)
        .set_text("The conditional assignment can be replaced with 'a = x and y'")
    ]),
    ([
        "def xxx(x, y):",
        "    if x:",
        "        a = y",
        "    else:",
        "        a = True"
    ], [
        lazy_problem().set_line(2)
        .set_text("The conditional assignment can be replaced with 'a = <negated x> or y'")
    ]),
    ([
        "def xxx(x, y, z):",
        "    if x:",
        "        a = y and z",
        "    else:",
        "        a = True"
    ], [
        lazy_problem().set_line(2)
        .set_text("The conditional assignment can be replaced with 'a = <negated x> or (y and z)'")
    ]),
    ([
        "def xxx(x, y, z):",
        "    if x:",
        "        a = y or z",
        "    else:",
        "        a = True"
    ], [
        lazy_problem().set_line(2)
        .set_text("The conditional assignment can be replaced with 'a = <negated x> or y or z'")
    ]),
])
def test_simplify_if_assigning_statement_conj_custom(lines: List[str], expected_output: List[Problem]) -> None:
    _test_simplify_if(lines, expected_output, "R6210")


@pytest.mark.parametrize("lines,expected_output", [
    ([
        "report = []",
        "which = 0",
        "report[which] = True if report[which] > \\",
        "    report[which] else False"
    ], [
        lazy_problem().set_line(3)
        .set_text("The if expression can be replaced with 'report[which] > report[which]'")
    ]),
    ([
        "report = []",
        "which = 0",
        "report[which], x = True if report[which] > report[which] else False, 0"
    ], [
        lazy_problem().set_line(3)
        .set_text("The if expression can be replaced with 'report[which] > report[which]'")
    ]),
    ([
        "report = []",
        "which = 0",
        "report[which], x = True if report[which] > report[which] else False, \\",
        "    False if report[which] <= report[which] else True"
    ], [
        lazy_problem().set_line(3)
        .set_text("The if expression can be replaced with 'report[which] > report[which]'"),
        lazy_problem().set_line(4)
        .set_text("The if expression can be replaced with '<negated report[which] <= report[which]>'")
    ]),
])
def test_simplify_if_expression_custom(lines: List[str], expected_output: List[Problem]) -> None:
    _test_simplify_if(lines, expected_output, "R6204")


@pytest.mark.parametrize("lines,expected_output", [
    ([
        "def xxx(x, y):",
        "    r = True if x else y"
    ], [
        lazy_problem().set_line(2)
        .set_text("The if expression can be replaced with 'x or y'")
    ]),
    ([
        "def xxx(x, y):",
        "    r = False if x else y"
    ], [
        lazy_problem().set_line(2)
        .set_text("The if expression can be replaced with '<negated x> and y'")
    ]),
    ([
        "def xxx(x, y):",
        "    r = y if x else False"
    ], [
        lazy_problem().set_line(2)
        .set_text("The if expression can be replaced with 'x and y'")
    ]),
    ([
        "def xxx(x, y):",
        "    r = y if x else True"
    ], [
        lazy_problem().set_line(2)
        .set_text("The if expression can be replaced with '<negated x> or y'")
    ]),
])
def test_simplify_if_expression_conj_custom(lines: List[str], expected_output: List[Problem]) -> None:
    _test_simplify_if(lines, expected_output, "R6209")


@pytest.mark.parametrize("lines,expected_output", [
    ([
        "def xxx(x, y):",
        "    if x:",
        "        pass",
        "    else:",
        "        return y"
    ], [
        lazy_problem().set_line(2)
        .set_text("Use 'if <negated x>: <else body>' instead of 'pass'")
    ]),
])
def test_simplify_if_pass_custom(lines: List[str], expected_output: List[Problem]) -> None:
    _test_simplify_if(lines, expected_output, "R6205")


@pytest.mark.parametrize("filename,expected_output", [
    ("015080-p4_geometry.py", [
        lazy_problem().set_code("R6207").set_line(14)
        .set_text("The if statement can be merged with the nested one to 'if len(sides) != len(set(sides))"
                  " and len(set(sides)) <= 3 and sides[1] == sides[2]:'"),
        lazy_problem().set_code("R6201").set_line(21)
        .set_text("The if statement can be replaced with 'return side_c == sides[2]'"),
        lazy_problem().set_code("R6201").set_line(32)
        .set_text("The if statement can be replaced with 'return a == b & a == c'"),
        lazy_problem().set_code("R6201").set_line(47)
        .set_text("The if statement can be replaced with 'return <negated duplicate(sides) < max(sides)>'"),
    ]),
    ("z202817-zkouska.py", [
        lazy_problem().set_code("R6208").set_line(76)
        .set_text("The if statement can be merged with the following one to "
                  "'if word == '' or word[len(word) - 1] == '.':'"),
        lazy_problem().set_code("R6205").set_line(82),
    ]),
    ("014823-p4_geometry.py", [
            lazy_problem().set_code("R6206").set_line(17)
            .set_text("Both branches should return a value explicitly (one returns implicit None)"),
            lazy_problem().set_code("R6206").set_line(25),
            lazy_problem().set_code("R6206").set_line(33),
            lazy_problem().set_code("R6201").set_line(43),
            lazy_problem().set_code("R6201").set_line(55),
    ]),
    ("024423-p5_credit.py", []),
    ("044669-p3_person_id.py", [lazy_problem().set_code("R6206").set_line(30)])
])
def test_simplify_if_files(filename: str, expected_output: List[Problem]) -> None:
    apply_and_lint(
        filename,
        [Arg(Option.PYLINT, "--enable=simplifiable-if")],
        expected_output
    )

@pytest.mark.parametrize("lines,expected_output", [
    ([
        "x = 7.8",
        "y = [-5.25, 2.3, 3, 4]",
        "z = -20",
        "a = abs(min(y)) > -4.47 and abs(min(y)) < 4.47",
        "c = int(z + abs(sum(reversed(sorted(y))))) < 8.56 and -8.56 < int(z + abs(sum(reversed(sorted(y)))))",
        "d = x + len(y) < 5 and x < 5 and x + len(y) > -10 and x > -5 and x + len(y) > -5",
    ], [
        lazy_problem().set_line(4)
        .set_text("'abs(min(y)) > -4.47 and abs(min(y)) < 4.47' can be replaced with 'abs(min(y)) < 4.47'"),
        lazy_problem().set_line(5)
        .set_text("'int(z + abs(sum(reversed(sorted(y))))) < 8.56 and int(z + abs(sum(reversed(sorted(y))))) > -8.56' can be replaced with 'abs(int(z + abs(sum(reversed(sorted(y)))))) < 8.56'"),
        lazy_problem().set_line(6)
        .set_text("'x + len(y) < 5 and x + len(y) > -10 and x + len(y) > -5' can be replaced with 'abs(x + len(y)) < 5'"),
        lazy_problem().set_line(6)
        .set_text("'x < 5 and x > -5' can be replaced with 'abs(x) < 5'"),
    ]),
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
        lazy_problem().set_line(3)
        .set_text("'x >= 2 or x <= -2' can be replaced with 'abs(x) >= 2'"),
        lazy_problem().set_line(4)
        .set_text("'x + len(y) > 4 or x + len(y) < -4' can be replaced with 'abs(x + len(y)) > 4'"),
        lazy_problem().set_line(5)
        .set_text("'x + 1 < -9 or x + 1 > 9' can be replaced with 'abs(x + 1) > 9'"),
        lazy_problem().set_line(6)
        .set_text("'x > 5 or x > 4 or x <= -7 or x >= 3 or x < -5 or x <= -3' can be replaced with 'abs(x) >= 3'"),
        lazy_problem().set_line(7)
        .set_text("'x > 7 or x < -7' can be replaced with 'abs(x) > 7'"),
        lazy_problem().set_line(8)
        .set_text("'y[0] >= 5 or y[0] <= -5' can be replaced with 'abs(y[0]) >= 5'"),
    ]),
])
def test_simplifiable_with_abs_custom(lines: List[str], expected_output: List[Problem]) -> None:
    create_apply_and_lint(
        lines,
        [Arg(Option.PYLINT, "--enable=simplifiable-with-abs")],
        expected_output,
    )

@pytest.mark.parametrize("filename,expected_output", [
    ("ffed796f7c-gps.py", [
        lazy_problem().set_line(23)
        .set_text("'float(y[1]) > 90 or float(y[1]) < -90 or float(y[1]) > 180 or float(y[1]) < -180' can be replaced with 'abs(float(y[1])) > 90'")
    ]),
    ("ffed796f7c-gps_tweaked.py", [
        lazy_problem().set_line(23)
        .set_text("'float(y[1]) > 90 or float(y[1]) < -90' can be replaced with 'abs(float(y[1])) > 90'"),
        lazy_problem().set_line(23)
        .set_text("'float(y[2]) > 180 or float(y[2]) < -180' can be replaced with 'abs(float(y[2])) > 180'")
    ])
])
def test_simplifiable_with_abs(filename: str, expected_output: List[Problem]) -> None:
    apply_and_lint(
        filename,
        [Arg(Option.PYLINT, "--enable=simplifiable-with-abs")],
        expected_output,
    )


@pytest.mark.parametrize("lines,expected_output", [
    ([
        "x = 7.8",
        "y = [-5.25, 2.3, 3, 4]",
        "a = x > -2 or x <= 6",
        "c = x >= 1 or x > 1",
        "d = x < 2 and x <= -5",
        "e = -(x - 1) > 5 or - (x- 1) < -5 or -(x-1) >= 4",
    ], [
        lazy_problem().set_line(3)
        .set_text("'x > -2 or x <= 6' can be simplified to 'True'. Simplify the condition if it is on purpose, or change it if it was not."),
        lazy_problem().set_line(4)
        .set_text("'x >= 1 or x > 1' can be simplified to 'x >= 1'. Simplify the condition if it is on purpose, or change it if it was not."),
        lazy_problem().set_line(5)
        .set_text("'x < 2 and x <= -5' can be simplified to 'x <= -5'. Simplify the condition if it is on purpose, or change it if it was not."),
        lazy_problem().set_line(6)
        .set_text("'-(x - 1) > 5 or -(x - 1) < -5 or -(x - 1) >= 4' can be simplified to '-(x - 1) < -5 or -(x - 1) >= 4'. Simplify the condition if it is on purpose, or change it if it was not."),
    ]),
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
        lazy_problem().set_line(10)
        .set_text("'person.age > 5 and person.age > 9' can be simplified to 'person.age > 9'. Simplify the condition if it is on purpose, or change it if it was not."),
    ]),
])
def test_redundant_compare(lines: List[str], expected_output: List[Problem]) -> None:
    create_apply_and_lint(
        lines,
        [Arg(Option.PYLINT, "--enable=redundant-compare-in-condition")],
        expected_output,
    )

@pytest.mark.parametrize("lines,expected_output", [
    ([
        "x = 7.8",
        "b = x > 4 or x > 0 or x < -1 or x < 0",
        "c = x >= 9 and x <= 9"
    ], [
        lazy_problem().set_line(2)
        .set_text("'x > 4 or x > 0 or x < -1 or x < 0' can be replaced with 'x != 0'"),
        lazy_problem().set_line(3)
        .set_text("'x >= 9 and x <= 9' can be replaced with 'x == 9'"),
    ]),
])
def test_using_compare_instead_of_equal(lines: List[str], expected_output: List[Problem]) -> None:
    create_apply_and_lint(
        lines,
        [Arg(Option.PYLINT, "--enable=using-compare-instead-of-equal")],
        expected_output,
    )

@pytest.mark.parametrize("lines,expected_output", [
    ([
        "a < b and a+50 < b",
        "j >= n//2 and i>=n//2",
        "i < len(t1) or len(t2) > i or i < 5 or i < max( x,y , z )",
        "- 1 + len(lst) > min(x, 3, y) or max(y, z) < -1 + len(lst) or (-1 + len(lst)) > min(x, z)"
    ], [
        lazy_problem().set_line(1)
        .set_text("'a < b and a + 50 < b' can be replaced with 'max(a, a + 50) < b'"),
        lazy_problem().set_line(2)
        .set_text("'j >= n // 2 and i >= n // 2' can be replaced with 'min(j, i) >= n // 2'"),
        lazy_problem().set_line(3)
        .set_text("'i < len(t1) or len(t2) > i or i < max(x, y, z) or i < 5' can be replaced with 'i < max(len(t1), len(t2), x, y, z, 5)'"),
        lazy_problem().set_line(4)
        .set_text("'-1 + len(lst) > min(x, 3, y) or max(y, z) < -1 + len(lst) or -1 + len(lst) > min(x, z)' can be replaced with 'min(x, 3, y, max(y, z), x, z) < -1 + len(lst)'"),
    ]),
])
def test_redundant_compare_with_variables(lines: List[str], expected_output: List[Problem]) -> None:
    create_apply_and_lint(
        lines,
        [Arg(Option.PYLINT, "--enable=redundant-compare-avoidable-with-max-min")],
        expected_output,
    )

@pytest.mark.parametrize("lines,expected_output", [
    ([
        "x = 1",
        "y = 7",
        "lst = [2, 3, 0, 8]",
        "x % 2 != 1 and y % 2 != 1 or x % 2 == 1 and y % 2 == 1",
        "x % 4 == 0 and y % 4 == 0 or x % 4 == 1 and y % 4 == 1 or x % 4 != 0 and y % 4 != 0 or x % 4 == 2 and y % 4 == 2 or x % 4 == 3 and y % 4 == 3",
        "len(lst) % 2 == 0 and (y - 2) % 2 == 0 or 1 == (y - 2) % 2 and len(lst) % 2 == 1 or (y - 2) % 2 == 0 and 0 == len(lst) % 2",
        "(x % 3 == 0 and 0 != y % 3) or (y % 3 == 0 and x % 3 != 0) or (x % 3 != 1 and y % 3 == 1) or (x % 3 == 1 and y % 3 == 2)",
        "x % 5 != 1 and y % 5 != 3 or x % 5 != 1 and y % 5 == 3 or x % 5 != 2 and y % 5 != 4",
        "x % 5 != 1 and y % 5 != 3 or x % 5 != 1 and y % 5 == 3 or x % 5 == 1 and y % 5 != 3 or x % 5 != 2 and y % 5 != 4",
        "x % 2 != 0 and y % 2 == 0 or 0 == x % 3 and y % 3 == 0 or y % 3 == 1 and x % 3 == 1 or x % 2 == 0 and y % 2 == 1 or x % 2 != 1 and y % 2 == 1 or y % 3 == 2 and x % 3 == 2"
    ], [
        lazy_problem().set_line(4)
        .set_text("'x % 2 != 1 and y % 2 != 1 or x % 2 == 1 and y % 2 == 1' can be replaced with 'x % 2 == y % 2'"),
        lazy_problem().set_line(5)
        .set_text("'x % 4 == 0 and y % 4 == 0 or x % 4 == 1 and y % 4 == 1 or x % 4 == 2 and y % 4 == 2 or x % 4 == 3 and y % 4 == 3' can be replaced with 'x % 4 == y % 4'"),
        lazy_problem().set_line(6)
        .set_text("'len(lst) % 2 == 0 and (y - 2) % 2 == 0 or 1 == (y - 2) % 2 and len(lst) % 2 == 1 or (y - 2) % 2 == 0 and 0 == len(lst) % 2' can be replaced with 'len(lst) % 2 == (y - 2) % 2'"),
        lazy_problem().set_line(7)
        .set_text("'x % 3 == 0 and 0 != y % 3 or y % 3 == 0 and x % 3 != 0 or x % 3 != 1 and y % 3 == 1 or x % 3 == 1 and y % 3 == 2' can be replaced with 'x % 3 != y % 3'"),
        lazy_problem().set_line(9)
        .set_text("'x % 5 != 1 and y % 5 != 3 or x % 5 != 1 and y % 5 == 3 or x % 5 == 1 and y % 5 != 3 or x % 5 != 2 and y % 5 != 4' can be replaced with 'True'"),
        lazy_problem().set_line(10)
        .set_text("'x % 2 != 0 and y % 2 == 0 or x % 2 == 0 and y % 2 == 1 or x % 2 != 1 and y % 2 == 1' can be replaced with 'x % 2 != y % 2'"),
        lazy_problem().set_line(10)
        .set_text("'0 == x % 3 and y % 3 == 0 or y % 3 == 1 and x % 3 == 1 or y % 3 == 2 and x % 3 == 2' can be replaced with 'x % 3 == y % 3'"),
    ]),
])
def test_simplifiable_test_by_equals(lines: List[str], expected_output: List[Problem]) -> None:
    create_apply_and_lint(
        lines,
        [Arg(Option.PYLINT, "--enable=simplifiable-test-by-equals")],
        expected_output,
    )
