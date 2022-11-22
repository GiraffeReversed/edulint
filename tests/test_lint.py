import pytest
from edulint.linters import Linter
from edulint.options import Option, get_option_parses
from edulint.config.arg import Arg
from edulint.config.config import Config, combine_and_translate
from edulint.config.config_translations import get_config_translations, get_ib111_translations
from edulint.linting.problem import Problem
from edulint.linting.linting import lint_one
from dataclasses import fields, replace
import os
import pathlib
from typing import List
import tempfile

LAZY_INT = -1
FILLER_CODE = ""


def lazy_equals(received: Problem, expected: Problem) -> None:
    if not any(expected.has_value(f.name) for f in fields(Problem)):
        assert False, f"unexpected problem {repr(received)}"

    copy = replace(received)
    for field in fields(Problem):
        if not expected.has_value(field.name):
            setattr(copy, field.name, getattr(expected, field.name))

    assert copy == expected


def lazy_problem() -> Problem:
    return Problem(None, "", LAZY_INT, LAZY_INT, None, "", LAZY_INT, LAZY_INT)  # type: ignore


def filler_problem() -> Problem:
    lazy = lazy_problem()
    lazy.code = FILLER_CODE
    return lazy


def fill(lst, len_):
    return lst + [filler_problem() for _ in range(len_ - len(lst))]


def lazy_equal(received: List[Problem], expected: List[Problem]) -> None:
    len_ = max(len(received), len(expected))
    for r, e in zip(fill(received, len_), fill(expected, len_)):
        lazy_equals(r, e)


def get_tests_path(filename: str) -> str:
    return str((pathlib.Path(__file__).parent / "data" / filename).resolve())


@pytest.mark.parametrize("filename,config,expected_output", [
    ("hello_world.py", Config(), []),
    ("z202817-zkouska.py", Config(), [
        lazy_problem().set_code("R6202").set_line(76),
        lazy_problem().set_code("R6205").set_line(82),
        lazy_problem().set_code("W0107").set_line(196)
    ]),
    ("z202817-zkouska.py", Config([Arg(Option.PYLINT, ["--enable=C0115"])]), [
        lazy_problem().set_code("R6202").set_line(76),
        lazy_problem().set_code("R6205").set_line(82),
        lazy_problem().set_code("C0115").set_line(122),
        lazy_problem().set_code("C0115").set_line(128),
        lazy_problem().set_code("W0107").set_line(196)
    ]),
    ("z202817-zkouska.py", Config([Arg(Option.PYLINT, ["--enable=C0115", "--disable=W0107"])]), [
        lazy_problem().set_code("R6202").set_line(76),
        lazy_problem().set_code("R6205").set_line(82),
        lazy_problem().set_code("C0115").set_line(122),
        lazy_problem().set_code("C0115").set_line(128)
    ]),
    ("z202817-zkouska.py",
     Config([Arg(Option.PYLINT, ["--disable=all"])]), []),
    ("002814-p1_trapezoid.py", Config(), [
        lazy_problem().set_code("F401").set_line(1),
        lazy_problem().set_code("F401").set_line(1),
        lazy_problem().set_code("E501").set_line(1),
        lazy_problem().set_code("W293").set_line(19),
        lazy_problem().set_code("E303").set_line(22),
    ])
])
def test_lint_basic(filename: str, config: Config, expected_output: List[Problem]) -> None:
    lazy_equal(lint_one(get_tests_path(filename), config), expected_output)


def apply_and_lint(filename: str, args: List[Arg], expected_output: List[Problem]) -> None:
    lazy_equal(
        lint_one(get_tests_path(filename),
                 combine_and_translate(args, get_option_parses(), get_config_translations(), get_ib111_translations())),
        expected_output
    )


def create_apply_and_lint(lines: List[str], args: List[Arg], expected_output: List[Problem]) -> None:
    tf = tempfile.NamedTemporaryFile("w+", delete=False)
    try:
        tf.writelines([line + "\n" for line in lines])
        tf.close()
        apply_and_lint(tf.name, args, expected_output)
    finally:
        os.remove(tf.name)


@pytest.mark.parametrize("filename,args,expected_output", [
    ("z202817-zkouska.py", [Arg(Option.ENHANCEMENT, True)], [
        lazy_problem().set_code("R6001").set_line(10),
        lazy_problem().set_code("R6202").set_line(76),
        lazy_problem().set_code("R6205").set_line(82),
        lazy_problem().set_code("R6001").set_line(175),
        lazy_problem().set_code("W0107").set_line(196),
    ]),
    ("z202817-zkouska.py", [Arg(Option.PYTHON_SPEC, True)], [
        lazy_problem().set_code("R6202").set_line(76),
        lazy_problem().set_code("R6102").set_line(80),
        lazy_problem().set_code("R6205").set_line(82),
        lazy_problem().set_code("R6101").set_line(171),
        lazy_problem().set_code("C0123").set_line(172),
        lazy_problem().set_code("W0107").set_line(196),
    ]),
    ("z202817-zkouska.py", [Arg(Option.PYLINT, "--disable=all"), Arg(Option.PYTHON_SPEC, True)], [
        lazy_problem().set_code("R6102").set_line(80),
        lazy_problem().set_code("R6101").set_line(171),
        lazy_problem().set_code("C0123").set_line(172),
    ]),
])
def test_translations(filename: str, args: List[Arg], expected_output: List[Problem]) -> None:
    apply_and_lint(filename, args, expected_output)


class TestIB111Week:
    @pytest.mark.parametrize("lines,args,expected_output", [
        ([
            "def swap(a, b):",
            "    tmp = a",
            "    a = b",
            "    b = tmp",
        ], [Arg(Option.PYTHON_SPEC, True)], [
            lazy_problem().set_code("R1712").set_line(2),
        ]), ([
            "def swap(a, b):",
            "    tmp = a",
            "    a = b",
            "    b = tmp",
        ], [Arg(Option.PYTHON_SPEC, True), Arg(Option.IB111_WEEK, "2")], [
        ]), ([
            "def swap(a, b):",
            "    tmp = a",
            "    a = b",
            "    b = tmp",
        ], [Arg(Option.PYTHON_SPEC, True), Arg(Option.IB111_WEEK, "3")], [
            lazy_problem().set_code("R1712").set_line(2),
        ]), ([
            "def is_one_or_two(n):",
            "    if n == 1 or n == 2:",
            "        return True",
            "    return False"
        ], [Arg(Option.PYTHON_SPEC, True), Arg(Option.IB111_WEEK, "6"), Arg(Option.PYLINT, "--disable=R6201")], [
        ]), ([
            "def is_one_or_two(n):",
            "    if n == 1 or n == 2:",
            "        return True",
            "    return False"
        ], [Arg(Option.PYTHON_SPEC, True), Arg(Option.IB111_WEEK, "7"), Arg(Option.PYLINT, "--disable=R6201")], [
            lazy_problem().set_code("R1714").set_line(2),
        ])
    ])
    def test_ib111_week_custom(self, lines: List[str], args: List[Arg], expected_output: List[Problem]) -> None:
        create_apply_and_lint(lines, args, expected_output)


@pytest.mark.parametrize("filename,args,expected_output", [
    ("014186-p2_nested.py", [Arg(Option.PYTHON_SPEC, True)], [
        lazy_problem().set_code("C0103").set_line(20),
        lazy_problem().set_code("C0103").set_line(21),
        lazy_problem().set_code("C0103").set_line(27),
        lazy_problem().set_code("C0103").set_line(28),
        lazy_problem().set_code("C0103").set_line(31),
        lazy_problem().set_code("C0103").set_line(34),
        lazy_problem().set_code("W0622").set_line(48),
    ]),
    ("custom_pep_assign.py", [Arg(Option.PYTHON_SPEC, True)], [
        lazy_problem().set_code("C0103").set_line(1),
    ])
])
def test_invalid_name(filename: str, args: List[Arg], expected_output: List[Problem]) -> None:
    apply_and_lint(filename, args, expected_output)


@pytest.mark.parametrize("filename,args,expected_output", [
    ("014180-p5_fibsum.py", [Arg(Option.ALLOWED_ONECHAR_NAMES, "")], [
        lazy_problem().set_code("C0104").set_line(6),
        lazy_problem().set_code("C0104").set_line(14)
    ]),
    ("014180-p5_fibsum.py", [Arg(Option.ALLOWED_ONECHAR_NAMES, "n")], [
        lazy_problem().set_code("C0104").set_line(14)
    ]),
    ("014180-p5_fibsum.py", [Arg(Option.ALLOWED_ONECHAR_NAMES, "i")], [
        lazy_problem().set_code("C0104").set_line(6)
    ]),
    ("014180-p5_fibsum.py", [Arg(Option.ALLOWED_ONECHAR_NAMES, "in")], [
    ])
])
def test_allowed_onechar_names(filename: str, args: List[Arg], expected_output: List[Problem]) -> None:
    apply_and_lint(filename, args, expected_output)


@pytest.mark.parametrize("filename,args,expected_output", [
    ("105119-p5_template.py", [Arg(Option.PYTHON_SPEC, True), Arg(Option.PYLINT, "--disable=C0200")], [
        lazy_problem().set_code("R1714").set_line(22)
        .set_text("Consider merging these comparisons with \"in\" to \"i not in '[]'\""),
        lazy_problem().set_code("R1714").set_line(35)
        .set_text("Consider merging these comparisons with \"in\" to 'i in (1, 2, 3)'"),
    ]),
])
def test_consider_using_in(filename: str, args: List[Arg], expected_output: List[Problem]) -> None:
    apply_and_lint(filename, args, expected_output)


class TestImproveFor:
    @pytest.mark.parametrize("lines,expected_output", [
        ([
            "A = list(range(10))",
            "B = []",
            "for x in range(len(A)):",
            "    for y in range(len(A)):",
            "        B.append(A[x])",
            "        B.append(y)"
        ], [
            lazy_problem().set_code("R6101").set_line(3)
            .set_text("Iterate directly: \"for var in A\" (with appropriate name for \"var\")"),
        ]), ([
            "A = list(range(10))",
            "B = []",
            "for x in range(len(A)):",
            "    x += 1",
            "    B.append(A[x])",
            "    B.append(A[x + 1])"
        ], [
        ]), ([
            "A = list(range(10))",
            "B = []",
            "for x in range(len(A)):",
            "    B.append(A[x + 1])",
        ], [
        ]), ([
            "A = list(range(10))",
            "for x in range(len(A)):",
            "    A[x] = A[x] + 1"
        ], [
            lazy_problem().set_code("R6102").set_line(2)
            .set_text("Iterate using enumerate: \"for x, var in enumerate(A)\" (with appropriate name for \"var\")"),
        ]), ([
            "A = list(range(10))",
            "B = []",
            "for x in range(len(A)):",
            "    for x in range(len(B)):",
            "        B.append(A[x])"
        ], [
        ])
    ])
    def test_improve_for_custom(self, lines: List[str], expected_output: List[Problem]) -> None:
        create_apply_and_lint(
            lines, [Arg(Option.PYLINT, "--enable=improve-for-loop")], expected_output)

    @pytest.mark.parametrize("filename,args,expected_output", [
        ("105119-p5_template.py", [Arg(Option.PYLINT, "--enable=iterate-directly")], [
        ]),
        ("015080-p4_geometry.py", [Arg(Option.PYLINT, "--enable=iterate-directly"),
                                   Arg(Option.PYLINT, "--disable=W0622,R1705,R1703,R6201,R6202")], [
        ]),
        ("014771-p2_nested.py", [Arg(Option.PYTHON_SPEC, True)], [
            lazy_problem().set_code("R6101").set_line(25)
            .set_text("Iterate directly: \"for var in A\" (with appropriate name for \"var\")"),
            lazy_problem().set_code("R6101").set_line(35)
            .set_text("Iterate directly: \"for var in A\" (with appropriate name for \"var\")"),
        ]),
        ("umime_count_a.py", [Arg(Option.PYLINT, "--enable=improve-for-loop"),
                              Arg(Option.FLAKE8, "--extend-ignore=E225")], [
            lazy_problem().set_code("R6101").set_line(3)
            .set_text("Iterate directly: \"for var in text\" (with appropriate name for \"var\")"),
        ]),
    ])
    def test_improve_for(self, filename: str, args: List[Arg], expected_output: List[Problem]) -> None:
        apply_and_lint(filename, args, expected_output)


class TestSimplifyIf:

    def _test_simplify_if(self, lines: List[str], expected_output: List[Problem], code: str) -> None:
        create_apply_and_lint(
            lines,
            [Arg(Option.PYLINT, "--disable=R1705"),
             Arg(Option.FLAKE8, "--extend-ignore=E501,F841")],
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
    def test_simplify_if_statement_single_var_custom(self, lines: List[str], expected_output: List[Problem]) -> None:
        self._test_simplify_if(lines, expected_output, "R6201")

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
    def test_simplify_if_statement_two_vars_custom(self, lines: List[str], expected_output: List[Problem]) -> None:
        self._test_simplify_if(lines, expected_output, "R6201")

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
    def test_simplify_if_statement_three_vars_custom(self, lines: List[str], expected_output: List[Problem]) -> None:
        self._test_simplify_if(lines, expected_output, "R6201")

    @pytest.mark.parametrize("lines,expected_output", [
        ([
            "def xxx(x, y):",
            "    if x:",
            "        if y:",
            "            return 0",
            "    return 1"
        ], [
            lazy_problem().set_line(2)
            .set_text("The if statement can be merged with the next to 'if x and y:'")
        ]),
        ([
            "def xxx(x, y):",
            "    if x:",
            "        return 0",
            "    if y:",
            "        return 0",
            "    return 1"
        ], [
            lazy_problem().set_line(2)
            .set_text("The if statement can be merged with the next to 'if x or y:'")
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
    def test_simplify_if_statement_multiconds_custom(self, lines: List[str], expected_output: List[Problem]) -> None:
        self._test_simplify_if(lines, expected_output, "R6202")

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
    def test_simplify_if_assigning_statement_custom(self, lines: List[str], expected_output: List[Problem]) -> None:
        self._test_simplify_if(lines, expected_output, "R6203")

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
    def test_simplify_if_expression_custom(self, lines: List[str], expected_output: List[Problem]) -> None:
        self._test_simplify_if(lines, expected_output, "R6204")

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
    def test_simplify_if_pass_custom(self, lines: List[str], expected_output: List[Problem]) -> None:
        self._test_simplify_if(lines, expected_output, "R6205")

    @pytest.mark.parametrize("filename,args,expected_output", [
        ("015080-p4_geometry.py", [Arg(Option.PYLINT, "--disable=W0622,R1705")], [
            lazy_problem().set_code("R6202").set_line(14)
            .set_text("The if statement can be merged with the next to 'if len(sides) != len(set(sides))"
                      " and len(set(sides)) <= 3 and sides[1] == sides[2]:'"),
            lazy_problem().set_code("R6201").set_line(21)
            .set_text("The if statement can be replaced with 'return side_c == sides[2]'"),
            lazy_problem().set_code("R6201").set_line(32)
            .set_text("The if statement can be replaced with 'return a == b & a == c'"),
            lazy_problem().set_code("R6201").set_line(47)
            .set_text("The if statement can be replaced with 'return <negated duplicate(sides) < max(sides)>'"),
        ]),
        ("z202817-zkouska.py", [Arg(Option.PYLINT, "--disable=all"), Arg(Option.PYLINT, "--enable=simplifiable-if")], [
            lazy_problem().set_code("R6202").set_line(76)
            .set_text("The if statement can be merged with the next to 'if word == '' or word[len(word) - 1] == '.':'"),
            lazy_problem().set_code("R6205").set_line(82),
        ]),
    ])
    def test_simplify_if(self, filename: str, args: List[Arg], expected_output: List[Problem]) -> None:
        apply_and_lint(filename, args, expected_output)


class TestNoWhileTrue:
    @pytest.mark.parametrize("lines,expected_output", [
        ([
            "def xxx(x):",
            "    while True:",
            "        if x:",
            "            break",
        ], [
            lazy_problem().set_line(2)
            .set_text("The while condition can be replaced with '<negated x>'")
        ]),
    ])
    def test_while_true_break(self, lines: List[str], expected_output: List[Problem]) -> None:
        create_apply_and_lint(
            lines,
            [Arg(Option.PYLINT, "--disable=R1705"),
             Arg(Option.FLAKE8, "--extend-ignore=E501,F841")],
            [p.set_code("R6301") for p in expected_output]
        )


@pytest.mark.parametrize("filename,args,expected_output", [
    ("umime_count_a.py", [
        Arg(Option.PYTHON_SPEC, True),
        Arg(Option.ALLOWED_ONECHAR_NAMES, ""),
        Arg(Option.ENHANCEMENT, True),
    ], [
        lazy_problem().set_code("C0104").set_line(2)
        .set_text("Disallowed single-character variable name \"a\", choose a more descriptive name"),
        lazy_problem().set_code("E225").set_line(2),
        lazy_problem().set_code("R6101").set_line(3)
        .set_text("Iterate directly: \"for var in text\" (with appropriate name for \"var\")"),
        lazy_problem().set_code("E225").set_line(4).set_column(19),
        lazy_problem().set_code("E225").set_line(4).set_column(35),
        lazy_problem().set_code("R6001").set_line(5)
        .set_text("Use augmenting assignment: \"a += 1\""),
    ]),
    ("umime_count_a_extended.py", [
        Arg(Option.PYTHON_SPEC, True),
        Arg(Option.ALLOWED_ONECHAR_NAMES, ""),
        Arg(Option.ENHANCEMENT, True),
    ], [
        lazy_problem().set_code("R6201").set_line(2)
        .set_text("The if statement can be replaced with 'return ch == 'a' or ch == 'A''"),
        lazy_problem().set_code("R1714").set_line(2)
        .set_text("Consider merging these comparisons with \"in\" to \"ch in 'aA'\""),
        lazy_problem().set_code("C0104").set_line(9)
        .set_text("Disallowed single-character variable name \"a\", choose a more descriptive name"),
        lazy_problem().set_code("R6101").set_line(10)
        .set_text("Iterate directly: \"for var in text\" (with appropriate name for \"var\")"),
        lazy_problem().set_code("R6001").set_line(12)
        .set_text("Use augmenting assignment: \"a += 1\""),
    ])
])
def test_umime_count_a(filename: str, args: List[Arg], expected_output: List[Problem]) -> None:
    apply_and_lint(filename, args, expected_output)


@pytest.mark.filterwarnings("ignore:The 'default' argument to fields is deprecated. Use 'dump_default' instead.")
def test_problem_can_be_dumped_to_json() -> None:
    problem = Problem(source=Linter.FLAKE8, path='path', line=5, column=1, code='E303',
                      text='too many blank lines (3)', end_line=None, end_column=None)
    out = problem.to_json(indent=2, sort_keys=True)  # type: ignore
    assert out == """{
  "code": "E303",
  "column": 1,
  "end_column": null,
  "end_line": null,
  "line": 5,
  "path": "path",
  "source": "flake8",
  "text": "too many blank lines (3)"
}"""

    out = Problem.schema().dumps([problem], indent=2, many=True, sort_keys=True)  # type: ignore
    assert out == """[
  {
    "code": "E303",
    "column": 1,
    "end_column": null,
    "end_line": null,
    "line": 5,
    "path": "path",
    "source": "flake8",
    "text": "too many blank lines (3)"
  }
]"""
