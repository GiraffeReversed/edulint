import pytest
from edulint.linters import Linter
from edulint.options import Option
from edulint.config.arg import Arg
from edulint.config.config import Config
from edulint.linting.problem import Problem
from edulint.linting.linting import lint_one
from utils import lazy_problem, lazy_equal, get_tests_path, apply_and_lint, create_apply_and_lint
from typing import List


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


@pytest.mark.parametrize("filename,args,expected_output", [
    ("z202817-zkouska.py", [Arg(Option.ENHANCEMENT, "on")], [
        lazy_problem().set_code("R6609").set_line(10),
        lazy_problem().set_code("R6202").set_line(76),
        lazy_problem().set_code("R6205").set_line(82),
        lazy_problem().set_code("R6609").set_line(175),
        lazy_problem().set_code("W0107").set_line(196),
    ]),
    ("z202817-zkouska.py", [Arg(Option.PYTHON_SPEC, "on")], [
        lazy_problem().set_code("R6202").set_line(76),
        lazy_problem().set_code("R6102").set_line(80),
        lazy_problem().set_code("R6205").set_line(82),
        lazy_problem().set_code("R6101").set_line(171),
        lazy_problem().set_code("C0123").set_line(172),
        lazy_problem().set_code("W0107").set_line(196),
    ]),
    ("z202817-zkouska.py", [Arg(Option.PYLINT, "--disable=all"), Arg(Option.PYTHON_SPEC, "on")], [
        lazy_problem().set_code("R6102").set_line(80),
        lazy_problem().set_code("R6101").set_line(171),
        lazy_problem().set_code("C0123").set_line(172),
    ]),
    ("z202817-zkouska.py", [Arg(Option.PYLINT, "--disable=all"), Arg(Option.PYTHON_SPEC, "off")], []),
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
        ], [Arg(Option.PYTHON_SPEC, "on")], [
            lazy_problem().set_code("R1712").set_line(2),
        ]), ([
            "def swap(a, b):",
            "    tmp = a",
            "    a = b",
            "    b = tmp",
        ], [Arg(Option.PYTHON_SPEC, "on"), Arg(Option.IB111_WEEK, "2")], [
        ]), ([
            "def swap(a, b):",
            "    tmp = a",
            "    a = b",
            "    b = tmp",
        ], [Arg(Option.PYTHON_SPEC, "on"), Arg(Option.IB111_WEEK, "3")], [
            lazy_problem().set_code("R1712").set_line(2),
        ]), ([
            "def is_one_or_two(n):",
            "    if n == 1 or n == 2:",
            "        return True",
            "    return False"
        ], [Arg(Option.PYTHON_SPEC, "on"), Arg(Option.IB111_WEEK, "6"), Arg(Option.PYLINT, "--disable=R6201")], [
        ]), ([
            "def is_one_or_two(n):",
            "    if n == 1 or n == 2:",
            "        return True",
            "    return False"
        ], [Arg(Option.PYTHON_SPEC, "on"), Arg(Option.IB111_WEEK, "7"), Arg(Option.PYLINT, "--disable=R6201")], [
            lazy_problem().set_code("R1714").set_line(2),
        ])
    ])
    def test_ib111_week_custom(self, lines: List[str], args: List[Arg], expected_output: List[Problem]) -> None:
        create_apply_and_lint(lines, args, expected_output)


@pytest.mark.parametrize("filename,args,expected_output", [
    ("014186-p2_nested.py", [Arg(Option.PYTHON_SPEC, "on")], [
        lazy_problem().set_code("C0103").set_line(20),
        lazy_problem().set_code("C0103").set_line(21),
        lazy_problem().set_code("C0103").set_line(27),
        lazy_problem().set_code("C0103").set_line(28),
        lazy_problem().set_code("C0103").set_line(31),
        lazy_problem().set_code("C0103").set_line(34),
        lazy_problem().set_code("W0622").set_line(48),
    ]),
    ("custom_pep_assign.py", [Arg(Option.PYTHON_SPEC, "on")], [
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
    ("105119-p5_template.py", [Arg(Option.PYTHON_SPEC, "on"), Arg(Option.PYLINT, "--disable=C0200")], [
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
            lines,
            [Arg(Option.PYLINT, "--disable=all"), Arg(Option.PYLINT, "--enable=improve-for-loop")],
            expected_output
        )

    @pytest.mark.parametrize("filename,args,expected_output", [
        ("105119-p5_template.py", [Arg(Option.PYLINT, "--enable=iterate-directly")], [
        ]),
        ("015080-p4_geometry.py", [Arg(Option.PYLINT, "--enable=iterate-directly"),
                                   Arg(Option.PYLINT, "--disable=W0622,R1705,R1703,R6201,R6202")], [
        ]),
        ("014771-p2_nested.py", [Arg(Option.PYTHON_SPEC, "on")], [
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
        (
            "014823-p4_geometry.py",
            [Arg(Option.PYLINT, "--disable=all"), Arg(Option.PYLINT, "--enable=simplifiable-if")],
            [
                lazy_problem().set_code("R6206").set_line(17)
                .set_text("Both branches should return a value explicitly (one returns implicit None)"),
                lazy_problem().set_code("R6206").set_line(25),
                lazy_problem().set_code("R6206").set_line(33),
                lazy_problem().set_code("R6201").set_line(43),
                lazy_problem().set_code("R6201").set_line(55),
            ]
        ),
        (
            "024423-p5_credit.py",
            [Arg(Option.PYLINT, "--disable=all"), Arg(Option.PYLINT, "--enable=simplifiable-if")],
            []
        ),
        (
            "044669-p3_person_id.py",
            [Arg(Option.PYLINT, "--disable=all"), Arg(Option.PYLINT, "--enable=simplifiable-if")],
            [lazy_problem().set_code("R6206").set_line(30)]
        )
    ])
    def test_simplify_if_files(self, filename: str, args: List[Arg], expected_output: List[Problem]) -> None:
        apply_and_lint(filename, args, expected_output)


class TestImproperLoop:
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

    @pytest.mark.parametrize("lines,expected_output", [
        ([
            "n = 10",
            "i = 0",
            "while i < n:",
            "    print('foo' + str(i))",
            "    i += 1",
        ], [
            lazy_problem().set_line(3)
            .set_text("Use for loop.")
        ]),
    ])
    def test_use_for_loop_custom(self, lines: List[str], expected_output: List[Problem]) -> None:
        create_apply_and_lint(
            lines,
            [Arg(Option.PYLINT, "--disable=all"),
             Arg(Option.PYLINT, "--enable=use-for-loop"),
             Arg(Option.NO_FLAKE8, "on")],
            [p.set_code("R6305") for p in expected_output]
        )

    @pytest.mark.parametrize("lines,expected_output", [
        ([
            "for i in range(10):",
            "    print('foo')",
            "    i += 1"
        ], [
            lazy_problem().set_line(3).set_text("Changing the control variable i of a for loop has no effect.")
        ]),
    ])
    def test_changing_control_variable_custom(self, lines: List[str], expected_output: List[Problem]) -> None:
        create_apply_and_lint(
            lines,
            [Arg(Option.PYLINT, "--disable=all"),
             Arg(Option.PYLINT, "--enable=changing-control-variable"),
             Arg(Option.NO_FLAKE8, "on")],
            [p.set_code("R6304") for p in expected_output]
        )

    @pytest.mark.parametrize("filename,expected_output", [
        ("hw14062.py", [
            lazy_problem().set_code("R6302").set_line(29)
            .set_text("Use tighter range boundaries, the first iteration never happens.")
        ]),
        ("hw34666.py", [
            lazy_problem().set_code("R6302").set_line(245)
            .set_text("Use tighter range boundaries, the last iteration never happens.")
        ]),
        ("m1630.py", [
            lazy_problem().set_code("R6302").set_line(107)
            .set_text("Use tighter range boundaries, the last iteration never happens.")
        ]),
    ])
    def test_tighter_bounds_files(self, filename: str, expected_output: List[Problem]) -> None:
        apply_and_lint(
            filename,
            [Arg(Option.PYLINT, "--disable=all"), Arg(Option.PYLINT, "--enable=use-tighter-boundaries")],
            expected_output
        )

    @pytest.mark.parametrize("filename,expected_output", [
        ("010666-even.py", [lazy_problem().set_line(9)]),
        ("012630-next.py", []),
        ("012986-nested.py", [lazy_problem().set_line(35)]),
        ("013450-next.py", []),
        ("014286-coins.py", []),
        ("014556-prime.py", [lazy_problem().set_line(13).set_text("Use for loop.")]),
        ("014962-sequence.py", [lazy_problem().set_line(18).set_text("Use for loop.")]),
        ("015794-amicable.py", [lazy_problem().set_line(14)]),
        ("016119-coins.py", [lazy_problem().set_line(22)]),
        ("017667-coins.py", []),
        ("023140-credit.py", []),
        ("043611-swap_columns.py", []),
    ])
    def test_use_for_loop_files(self, filename: str, expected_output: List[Problem]) -> None:
        apply_and_lint(
            filename,
            [Arg(Option.PYLINT, "--disable=all"), Arg(Option.PYLINT, "--enable=use-for-loop")],
            [problem.set_code("R6305") for problem in expected_output]
        )

    @pytest.mark.parametrize("filename,expected_output", [
        ("034636-right_cellular.py", []),
        ("104526-subset_sum.py", [
            lazy_problem().set_line(17)
            .set_text("Iterated structure nums is being modified inside the for loop body. "
                      "Use while loop or iterate over a copy."),
            lazy_problem().set_line(22)
        ]),
        ("035794-partition.py", []),
        ("hw24328.py", [
            lazy_problem().set_line(52)
            .set_text("Iterated structure row is being modified inside the for loop body. "
                      "Use while loop or iterate over a copy."),
            lazy_problem().set_line(53),
            lazy_problem().set_line(56),
            lazy_problem().set_line(99),
            lazy_problem().set_line(100),
            lazy_problem().set_line(103),
        ]),
        ("hw44081.py", [
            lazy_problem().set_line(149)
            .set_text("Iterated structure traders is being modified inside the for loop body. "
                      "Use while loop or iterate over a copy.")
        ]),
    ])
    def test_modifying_iterated_files(self, filename: str, expected_output: List[Problem]) -> None:
        apply_and_lint(
            filename,
            [Arg(Option.PYLINT, "--disable=all"), Arg(Option.PYLINT, "--enable=modifying-iterated-structure")],
            [problem.set_code("R6303") for problem in expected_output]
        )

    @pytest.mark.parametrize("filename,expected_output", [
        ("hw33176.py", []),
        ("m4521.py", [
            lazy_problem().set_line(117).set_text("Inner for loop shadows outer for loop's control variable i.")
        ])
    ])
    def test_shadowed_control_var_files(self, filename: str, expected_output: List[Problem]) -> None:
        apply_and_lint(
            filename,
            [Arg(Option.PYLINT, "--disable=all"), Arg(Option.PYLINT, "--enable=loop-shadows-control-variable"),
             Arg(Option.NO_FLAKE8, "on")],
            expected_output
        )

    @pytest.mark.parametrize("filename,expected_output", [
        ("014659-next.py", [
            lazy_problem().set_line(24).set_text("Changing the control variable i of a for loop has no effect.")
        ]),
        ("hw24226.py", [
            lazy_problem().set_line(77).set_text("Changing the control variable j of a for loop has no effect."),
            lazy_problem().set_line(101).set_text("Changing the control variable p of a for loop has no effect."),
        ]),
        ("hw24387.py", [
            lazy_problem().set_line(98).set_text("Changing the control variable i of a for loop has no effect."),
            lazy_problem().set_line(129),
        ]),
        ("hw34406.py", []),
        ("hw34666.py", [
            lazy_problem().set_line(40),
            lazy_problem().set_line(43),
            lazy_problem().set_line(51),
            lazy_problem().set_line(54),
            lazy_problem().set_line(57),
            lazy_problem().set_line(71),
            lazy_problem().set_line(74),
            lazy_problem().set_line(77),
        ]),
    ])
    def test_changing_control_var_files(self, filename: str, expected_output: List[Problem]) -> None:
        apply_and_lint(
            filename,
            [Arg(Option.PYLINT, "--disable=all"), Arg(Option.PYLINT, "--enable=changing-control-variable")],
            [problem.set_code("R6304") for problem in expected_output]
        )


class TestNoGlobals:
    @pytest.mark.parametrize("lines,expected_output", [
        ([
            "x = 0",
            "def foo():",
            "    global x",
            "    x = 1"
        ], [
            lazy_problem().set_line(1)
            .set_text("Do not use global variables; you use x, modifying it for example at line 4.")
        ]),
        ([
            "x = 0",
            "def foo():",
            "    nonlocal x",
            "    x = 1"
        ], [
            lazy_problem().set_line(1)
            .set_text("Do not use global variables; you use x, modifying it for example at line 4.")
        ]),
        ([
            "x = 0",
            "def foo():",
            "    x = 1",
            "    def bar():",
            "        nonlocal x",
            "        x = 2"
        ], [
        ]),
        ([
            "x = []",
            "def foo():",
            "    x.append(1)"
        ], [
            lazy_problem().set_line(1)
            .set_text("Do not use global variables; you use x, modifying it for example at line 3.")
        ]),
        ([
            "x = None",
            "def foo():",
            "    x.y = 1"
        ], [
            lazy_problem().set_line(1)
            .set_text("Do not use global variables; you use x, modifying it for example at line 3.")
        ]),
        ([
            "if __name__ == '__main__':",
            "    test = 1",
            "    test = 2",
        ], [
        ]),
    ])
    def test_no_globals_custom(self, lines: List[str], expected_output: List[Problem]) -> None:
        create_apply_and_lint(
            lines,
            [Arg(Option.PYLINT, "--disable=all"),
             Arg(Option.PYLINT, "--enable=no-global-variables"),
             Arg(Option.NO_FLAKE8, "on")],
            [p.set_code("R6401") for p in expected_output]
        )

    @pytest.mark.parametrize("filename,expected_output", [
        ("054141-p1_database.py", []),
        ("054103-p1_database.py", []),
        ("hw14699.py", []),
        ("014466-fibfibsum.py", [
            lazy_problem().set_code("R6401").set_line(11)
            .set_text("Do not use global variables; you use fib, modifying it for example at line 18.")
        ]),
        ("021752-cards.py", [
            lazy_problem().set_code("R6401").set_line(7)
            .set_text("Do not use global variables; you use first_num, modifying it for example at line 27."),
            lazy_problem().set_code("R6401").set_line(8)
            .set_text("Do not use global variables; you use digits, modifying it for example at line 20."),
        ]),
        ("088952-p2_extremes.py", []),
        ("s10265-d_mancala.py", []),
    ])
    def test_no_globals_files(self, filename: str, expected_output: List[Problem]) -> None:
        apply_and_lint(
            filename,
            [Arg(Option.PYLINT, "--disable=all"), Arg(Option.PYLINT, "--enable=no-global-variables")],
            expected_output
        )


@pytest.mark.parametrize("filename,args,expected_output", [
    ("umime_count_a.py", [
        Arg(Option.PYTHON_SPEC, "on"),
        Arg(Option.ALLOWED_ONECHAR_NAMES, ""),
        Arg(Option.ENHANCEMENT, "on"),
    ], [
        lazy_problem().set_code("C0104").set_line(2)
        .set_text("Disallowed single-character variable name \"a\", choose a more descriptive name"),
        lazy_problem().set_code("E225").set_line(2),
        lazy_problem().set_code("R6101").set_line(3)
        .set_text("Iterate directly: \"for var in text\" (with appropriate name for \"var\")"),
        lazy_problem().set_code("E225").set_line(4).set_column(19),
        lazy_problem().set_code("E225").set_line(4).set_column(35),
        lazy_problem().set_code("R6609").set_line(5)
        .set_text("Use augmenting assignment: 'a += 1'"),
    ]),
    ("umime_count_a_extended.py", [
        Arg(Option.PYTHON_SPEC, "on"),
        Arg(Option.ALLOWED_ONECHAR_NAMES, ""),
        Arg(Option.ENHANCEMENT, "on"),
    ], [
        lazy_problem().set_code("R6201").set_line(2)
        .set_text("The if statement can be replaced with 'return ch == 'a' or ch == 'A''"),
        lazy_problem().set_code("R1714").set_line(2)
        .set_text("Consider merging these comparisons with \"in\" to \"ch in 'aA'\""),
        lazy_problem().set_code("C0104").set_line(9)
        .set_text("Disallowed single-character variable name \"a\", choose a more descriptive name"),
        lazy_problem().set_code("R6101").set_line(10)
        .set_text("Iterate directly: \"for var in text\" (with appropriate name for \"var\")"),
        lazy_problem().set_code("R6609").set_line(12)
        .set_text("Use augmenting assignment: 'a += 1'"),
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
