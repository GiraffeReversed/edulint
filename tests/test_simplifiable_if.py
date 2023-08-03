import pytest
from edulint.options import Option
from edulint.config.arg import Arg
from edulint.linting.problem import Problem
from utils import lazy_problem, apply_and_lint, create_apply_and_lint
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
        .set_text("The conditional assignment can be replace with 'triangle_is_righ = c**2 == a**2 "
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
        .set_text("The conditional assignment can be replace with 'a = x or y'")
    ]),
    ([
        "def xxx(x, y):",
        "    if x:",
        "        a = False",
        "    else:",
        "        a = y"
    ], [
        lazy_problem().set_line(2)
        .set_text("The conditional assignment can be replace with 'a = <negated x> and y'")
    ]),
    ([
        "def xxx(x, y):",
        "    if x:",
        "        a = y",
        "    else:",
        "        a = False"
    ], [
        lazy_problem().set_line(2)
        .set_text("The conditional assignment can be replace with 'a = x and y'")
    ]),
    ([
        "def xxx(x, y):",
        "    if x:",
        "        a = y",
        "    else:",
        "        a = True"
    ], [
        lazy_problem().set_line(2)
        .set_text("The conditional assignment can be replace with 'a = <negated x> or y'")
    ]),
    ([
        "def xxx(x, y, z):",
        "    if x:",
        "        a = y and z",
        "    else:",
        "        a = True"
    ], [
        lazy_problem().set_line(2)
        .set_text("The conditional assignment can be replace with 'a = <negated x> or (y and z)'")
    ]),
    ([
        "def xxx(x, y, z):",
        "    if x:",
        "        a = y or z",
        "    else:",
        "        a = True"
    ], [
        lazy_problem().set_line(2)
        .set_text("The conditional assignment can be replace with 'a = <negated x> or y or z'")
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
