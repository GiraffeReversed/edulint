import pytest
from edulint.linters import Linter
from edulint.options import Option
from edulint.config.arg import Arg
from edulint.linting.problem import Problem
from utils import lazy_problem, apply_and_lint, create_apply_and_lint, just_lint
from typing import List


@pytest.mark.parametrize(
    "filename,args,expected_output",
    [
        ("hello_world.py", [], []),
        (
            "z202817-zkouska.py",
            [],
            [
                lazy_problem().set_code("R6609").set_line(10),
                lazy_problem().set_code("R6303").set_line(42),
                lazy_problem().set_code("R6205").set_line(82),
                lazy_problem().set_code("R6101").set_line(171),
                lazy_problem().set_code("W0107").set_line(196),
            ],
        ),
        (
            "z202817-zkouska.py",
            [Arg(Option.PYLINT, "--enable=C0115")],
            [
                lazy_problem().set_code("R6609").set_line(10),
                lazy_problem().set_code("R6303").set_line(42),
                lazy_problem().set_code("R6205").set_line(82),
                lazy_problem().set_code("C0115").set_line(122),
                lazy_problem().set_code("C0115").set_line(128),
                lazy_problem().set_code("R6101").set_line(171),
                lazy_problem().set_code("W0107").set_line(196),
            ],
        ),
        (
            "z202817-zkouska.py",
            [Arg(Option.PYLINT, "--enable=C0115"), Arg(Option.PYLINT, "--disable=W0107,R6609")],
            [
                lazy_problem().set_code("R6303").set_line(42),
                lazy_problem().set_code("R6205").set_line(82),
                lazy_problem().set_code("C0115").set_line(122),
                lazy_problem().set_code("C0115").set_line(128),
                lazy_problem().set_code("R6101").set_line(171),
            ],
        ),
        ("z202817-zkouska.py", [Arg(Option.PYLINT, "--disable=all")], []),
        (
            "002814-p1_trapezoid.py",
            [],
            [
                lazy_problem().set_code("F401").set_line(1),
                lazy_problem().set_code("F401").set_line(1),
                lazy_problem().set_code("E501").set_line(1),
                lazy_problem().set_code("W293").set_line(19),
                lazy_problem().set_code("E303").set_line(22),
            ],
        ),
    ],
)
def test_lint_basic(filename: str, args: List[Arg], expected_output: List[Problem]) -> None:
    apply_and_lint(
        filename,
        args + [Arg(Option.FLAKE8, "--extend-ignore=E721")],
        expected_output,
        from_empty=False,
    )


@pytest.mark.parametrize(
    "filename,args,expected_output",
    [
        (
            "z202817-zkouska.py",
            [Arg(Option.SET_GROUPS, "enhancement")],
            [
                lazy_problem().set_code("R6609").set_line(10),
                lazy_problem().set_code("R6303").set_line(42),
                lazy_problem().set_code("R6208").set_line(76),
                lazy_problem().set_code("R6205").set_line(82),
                lazy_problem().set_code("R6101").set_line(171),
                lazy_problem().set_code("W0107").set_line(196),
            ],
        ),
        (
            "z202817-zkouska.py",
            [Arg(Option.SET_GROUPS, "python-specific")],
            [
                lazy_problem().set_code("R6609").set_line(10),
                lazy_problem().set_code("R6303").set_line(42),
                # lazy_problem().set_code("R6102").set_line(80), TODO differentiate?
                lazy_problem().set_code("R6205").set_line(82),
                lazy_problem().set_code("R6101").set_line(171),
                lazy_problem().set_code("C0123").set_line(172),
                lazy_problem().set_code("W0107").set_line(196),
            ],
        ),
        (
            "z202817-zkouska.py",
            [Arg(Option.PYLINT, "--disable=all"), Arg(Option.SET_GROUPS, "python-specific")],
            [
                lazy_problem().set_code("C0123").set_line(172),
            ],
        ),
        (
            "z202817-zkouska.py",
            [Arg(Option.PYLINT, "--disable=all"), Arg(Option.SET_GROUPS, "")],
            [],
        ),
        (
            "hw34406.py",
            [Arg(Option.PYLINT, "--disable=all"), Arg(Option.SET_GROUPS, "complexity")],
            [
                lazy_problem().set_line(240).set_code("R0913"),
                lazy_problem().set_line(266).set_code("R0911"),
                lazy_problem().set_line(266).set_code("R0912"),
                lazy_problem().set_line(343).set_code("R0912"),
                lazy_problem().set_line(343).set_code("R0915"),
                lazy_problem().set_line(387).set_code("R1702"),
                lazy_problem().set_line(387).set_code("R1702"),
                lazy_problem().set_line(387).set_code("R1702"),
            ],
        ),
    ],
)
def test_translations(filename: str, args: List[Arg], expected_output: List[Problem]) -> None:
    apply_and_lint(
        filename,
        args + [Arg(Option.FLAKE8, "--extend-ignore=E721")],
        expected_output,
        from_empty=False,
    )


class TestIB111Week:
    @pytest.mark.parametrize(
        "lines,args,expected_output",
        [
            (
                [
                    "def swap(a, b):",
                    "    tmp = a",
                    "    a = b",
                    "    b = tmp",
                ],
                [Arg(Option.SET_GROUPS, "python-specific")],
                [
                    lazy_problem().set_code("R1712").set_line(2),
                ],
            ),
            (
                [
                    "def swap(a, b):",
                    "    tmp = a",
                    "    a = b",
                    "    b = tmp",
                ],
                [
                    Arg(Option.SET_GROUPS, "python-specific"),
                    Arg(Option.SET_GROUPS, "ib111-week-02"),
                ],
                [],
            ),
            (
                [
                    "def swap(a, b):",
                    "    tmp = a",
                    "    a = b",
                    "    b = tmp",
                ],
                [
                    Arg(Option.SET_GROUPS, "python-specific,ib111-week-03"),
                ],
                [
                    lazy_problem().set_code("R1712").set_line(2),
                ],
            ),
            (
                [
                    "def is_one_or_two(n):",
                    "    if n == 1 or n == 2:",
                    "        return True",
                    "    return False",
                ],
                [
                    Arg(Option.SET_GROUPS, "python-specific,ib111-week-06"),
                    Arg(Option.PYLINT, "--disable=R6201"),
                ],
                [],
            ),
            (
                [
                    "def is_one_or_two(n):",
                    "    if n == 1 or n == 2:",
                    "        return True",
                    "    return False",
                ],
                [
                    Arg(Option.SET_GROUPS, "python-specific,ib111-week-07"),
                    Arg(Option.PYLINT, "--disable=R6201"),
                ],
                [
                    lazy_problem().set_code("R1714").set_line(2),
                ],
            ),
        ],
    )
    def test_ib111_week_custom(
        self, lines: List[str], args: List[Arg], expected_output: List[Problem]
    ) -> None:
        create_apply_and_lint(
            lines,
            [Arg(Option.CONFIG, "tests/ib111-weeks.toml")] + args,
            expected_output,
            from_empty=False,
        )


@pytest.mark.parametrize(
    "lines,expected_output",
    [
        (["class A:", "    pass"], []),
        (["class _:", "    pass"], []),
        (["class a:", "    pass"], [lazy_problem().set_line(1)]),
        (["class class_name:", "    pass"], [lazy_problem().set_line(1)]),
        (["class CLASS_NAME:", "    pass"], [lazy_problem().set_line(1)]),
        (["def fun():", "    a = 5"], []),
        (["def fun():", "    local_variable = 5"], []),
        (["def fun():", "    _ = 5"], []),
        (["def fun():", "    A = 5"], [lazy_problem().set_line(2)]),
        (["def fun():", "    LOCAL_VARIABLE = 5"], [lazy_problem().set_line(2)]),
        (["def fun():", "    localVariable = 5"], [lazy_problem().set_line(2)]),
        (["def f():", "    pass"], []),
        (["def just_fun():", "    pass"], []),
        (["def _():", "    pass"], []),
        (["def F():", "    pass"], [lazy_problem().set_line(1)]),
        (["def JUST_FUN():", "    pass"], [lazy_problem().set_line(1)]),
        (["def JustFun():", "    pass"], [lazy_problem().set_line(1)]),
        (["A = 5"], []),
        (["GLOBAL_VARIABLE = 1"], []),
        (["TypeAlias = int"], []),
        (["_ = int"], []),
        (["a = 1"], [lazy_problem().set_line(1)]),
        (["global_variable = 1"], [lazy_problem().set_line(1)]),
    ],
)
def test_invalid_name_custom(lines: List[str], expected_output: List[Problem]) -> None:
    create_apply_and_lint(lines, [Arg(Option.PYLINT, "--enable=invalid-name")], expected_output)


@pytest.mark.parametrize(
    "filename,args,expected_output",
    [
        (
            "014186-p2_nested.py",
            [Arg(Option.SET_GROUPS, "python-specific")],
            [
                lazy_problem().set_code("C0103").set_line(20),
                lazy_problem().set_code("C0103").set_line(21),
                lazy_problem().set_code("C0103").set_line(27),
                lazy_problem().set_code("C0103").set_line(28),
                lazy_problem().set_code("C0103").set_line(31),
                lazy_problem().set_code("C0103").set_line(34),
                lazy_problem().set_code("W0622").set_line(48),
            ],
        ),
        (
            "custom_pep_assign.py",
            [Arg(Option.SET_GROUPS, "python-specific")],
            [
                lazy_problem().set_code("C0103").set_line(1),
            ],
        ),
    ],
)
def test_invalid_name(filename: str, args: List[Arg], expected_output: List[Problem]) -> None:
    apply_and_lint(filename, args, expected_output, from_empty=False)


@pytest.mark.parametrize(
    "filename,args,expected_output",
    [
        (
            "014180-p5_fibsum.py",
            [Arg(Option.ALLOWED_ONECHAR_NAMES, "")],
            [
                lazy_problem().set_code("C0104").set_line(6),
                lazy_problem().set_code("C0104").set_line(14),
            ],
        ),
        (
            "014180-p5_fibsum.py",
            [Arg(Option.ALLOWED_ONECHAR_NAMES, "n")],
            [lazy_problem().set_code("C0104").set_line(14)],
        ),
        (
            "014180-p5_fibsum.py",
            [Arg(Option.ALLOWED_ONECHAR_NAMES, "i")],
            [lazy_problem().set_code("C0104").set_line(6)],
        ),
        ("014180-p5_fibsum.py", [Arg(Option.ALLOWED_ONECHAR_NAMES, "in")], []),
    ],
)
def test_allowed_onechar_names(
    filename: str, args: List[Arg], expected_output: List[Problem]
) -> None:
    apply_and_lint(
        filename, [Arg(Option.PYLINT, "--enable=disallowed-name")] + args, expected_output
    )


@pytest.mark.parametrize(
    "filename,args,expected_output",
    [
        (
            "105119-p5_template.py",
            [Arg(Option.PYLINT, "--enable=R1714")],
            [
                lazy_problem()
                .set_code("R1714")
                .set_line(22)
                .set_text("Consider merging these comparisons with 'in' by using 'i not in '[]''"),
                lazy_problem()
                .set_code("R1714")
                .set_line(35)
                .set_text("Consider merging these comparisons with 'in' by using 'i in (1, 2, 3)'"),
            ],
        ),
    ],
)
def test_consider_using_in(filename: str, args: List[Arg], expected_output: List[Problem]) -> None:
    apply_and_lint(filename, args, expected_output)


class TestImproveFor:
    @pytest.mark.parametrize(
        "lines,expected_output",
        [
            (
                [
                    "A = list(range(10))",
                    "B = []",
                    "for x in range(len(A)):",
                    "    for y in range(len(A)):",
                    "        B.append(A[x])",
                    "        B.append(y)",
                ],
                [
                    lazy_problem()
                    .set_code("R6101")
                    .set_line(3)
                    .set_text('Iterate directly: "for var in A" (with appropriate name for "var")'),
                ],
            ),
            (["A = list(range(10))", "for i in range(5, len(A)):", "    print(A[i])"], []),
            (["A = list(range(10))", "a = 5", "for i in range(a, len(A)):", "    print(A[i])"], []),
            (
                [
                    "A = list(range(10))",
                    "a = 5",
                    "for i in range(a, len(A)):",
                    "    print(i, A[i])",
                ],
                [],
            ),
            (
                [
                    "A = list(range(10))",
                    "B = []",
                    "for x in range(len(A)):",
                    "    x += 1",
                    "    B.append(A[x])",
                    "    B.append(A[x + 1])",
                ],
                [],
            ),
            (
                [
                    "A = list(range(10))",
                    "B = []",
                    "for x in range(len(A)):",
                    "    B.append(A[x + 1])",
                ],
                [],
            ),
            (
                ["A = list(range(10))", "for x in range(len(A)):", "    A[x] = A[x] + 1"],
                [
                    lazy_problem()
                    .set_code("R6102")
                    .set_line(2)
                    .set_text(
                        'Iterate using enumerate: "for x, var in enumerate(A)" (with appropriate name for "var")'
                    ),
                ],
            ),
            (
                [
                    "A = list(range(10))",
                    "B = []",
                    "for x in range(len(A)):",
                    "    for x in range(len(B)):",
                    "        B.append(A[x])",
                ],
                [],
            ),
        ],
    )
    def test_improve_for_custom(self, lines: List[str], expected_output: List[Problem]) -> None:
        create_apply_and_lint(
            lines, [Arg(Option.PYLINT, "--enable=improve-for-loop")], expected_output
        )

    @pytest.mark.parametrize(
        "filename,args,expected_output",
        [
            ("105119-p5_template.py", [Arg(Option.PYLINT, "--enable=use-foreach")], []),
            (
                "015080-p4_geometry.py",
                [
                    Arg(Option.PYLINT, "--enable=use-foreach"),
                    Arg(Option.PYLINT, "--disable=W0622,R1705,R1703,R6201,R6202"),
                ],
                [],
            ),
            (
                "014771-p2_nested.py",
                [Arg(Option.PYLINT, "--enable=use-foreach")],
                [
                    lazy_problem()
                    .set_code("R6101")
                    .set_line(25)
                    .set_text('Iterate directly: "for var in A" (with appropriate name for "var")'),
                    lazy_problem()
                    .set_code("R6101")
                    .set_line(35)
                    .set_text('Iterate directly: "for var in A" (with appropriate name for "var")'),
                ],
            ),
            ("045294-p4_vigenere.py", [Arg(Option.PYLINT, "--enable=use-foreach")], []),
            (
                "umime_count_a.py",
                [
                    Arg(Option.PYLINT, "--enable=improve-for-loop"),
                    Arg(Option.FLAKE8, "--extend-ignore=E225"),
                ],
                [
                    lazy_problem()
                    .set_code("R6101")
                    .set_line(3)
                    .set_text(
                        'Iterate directly: "for var in text" (with appropriate name for "var")'
                    ),
                ],
            ),
            ("03-d4_points.py", [Arg(Option.PYLINT, "--enable=use-enumerate")], []),
            (
                "046542-polybius.py",
                [Arg(Option.PYLINT, "--enable=improve-for-loop")],
                [
                    lazy_problem().set_line(44),
                    lazy_problem().set_line(45),
                    lazy_problem().set_line(67),
                    lazy_problem().set_line(68),
                ],
            ),
        ],
    )
    def test_improve_for(
        self, filename: str, args: List[Arg], expected_output: List[Problem]
    ) -> None:
        apply_and_lint(filename, args, expected_output)


class TestPyTA:
    @pytest.mark.parametrize(
        "lines,expected_output",
        [
            (["from typing import Tuple", "Point = Tuple[int, int]"], []),
            (["if 0 == 1:", "    print('noooooooo')"], [lazy_problem().set_line(1)]),
        ],
    )
    def test_forbidden_toplevel_code_custom(
        self, lines: List[str], expected_output: List[Problem]
    ) -> None:
        create_apply_and_lint(
            lines,
            [Arg(Option.PYLINT, "--enable=forbidden-top-level-code")],
            [p.set_code("E9992") for p in expected_output],
        )


class TestNoGlobals:
    @pytest.mark.parametrize(
        "lines,expected_output",
        [
            (
                ["x = 0", "def foo():", "    global x", "    x = 1"],
                [
                    lazy_problem()
                    .set_line(1)
                    .set_text(
                        "Do not use global variables; you use x, modifying it for example at line 4."
                    )
                ],
            ),
            (
                ["x = 0", "def foo():", "    nonlocal x", "    x = 1"],
                [
                    lazy_problem()
                    .set_line(1)
                    .set_text(
                        "Do not use global variables; you use x, modifying it for example at line 4."
                    )
                ],
            ),
            (
                [
                    "x = 0",
                    "def foo():",
                    "    x = 1",
                    "    def bar():",
                    "        nonlocal x",
                    "        x = 2",
                ],
                [],
            ),
            (
                ["x = []", "def foo():", "    x.append(1)"],
                [
                    lazy_problem()
                    .set_line(1)
                    .set_text(
                        "Do not use global variables; you use x, modifying it for example at line 3."
                    )
                ],
            ),
            (
                ["x = None", "def foo():", "    x.y = 1"],
                [
                    lazy_problem()
                    .set_line(1)
                    .set_text(
                        "Do not use global variables; you use x, modifying it for example at line 3."
                    )
                ],
            ),
            (
                [
                    "if __name__ == '__main__':",
                    "    test = 1",
                    "    test = 2",
                ],
                [],
            ),
        ],
    )
    def test_no_globals_custom(self, lines: List[str], expected_output: List[Problem]) -> None:
        create_apply_and_lint(
            lines,
            [Arg(Option.PYLINT, "--enable=no-global-variables")],
            [p.set_code("R6401") for p in expected_output],
        )

    @pytest.mark.parametrize(
        "filename,expected_output",
        [
            ("054141-p1_database.py", []),
            ("054103-p1_database.py", []),
            ("hw14699.py", []),
            (
                "014466-fibfibsum.py",
                [
                    lazy_problem()
                    .set_code("R6401")
                    .set_line(11)
                    .set_text(
                        "Do not use global variables; you use fib, modifying it for example at line 18."
                    )
                ],
            ),
            (
                "021752-cards.py",
                [
                    lazy_problem()
                    .set_code("R6401")
                    .set_line(7)
                    .set_text(
                        "Do not use global variables; you use first_num, modifying it for example at line 27."
                    ),
                    lazy_problem()
                    .set_code("R6401")
                    .set_line(8)
                    .set_text(
                        "Do not use global variables; you use digits, modifying it for example at line 20."
                    ),
                ],
            ),
            ("088952-p2_extremes.py", []),
            ("s10265-d_mancala.py", []),
        ],
    )
    def test_no_globals_files(self, filename: str, expected_output: List[Problem]) -> None:
        apply_and_lint(
            filename, [Arg(Option.PYLINT, "--enable=no-global-variables")], expected_output
        )


class TestLongCode:
    @pytest.mark.parametrize(
        "filename,expected_output",
        [
            (
                "hw48505.py",
                [
                    lazy_problem().set_line(80),
                    lazy_problem().set_line(196),
                ],
            ),
        ],
    )
    def test_long_function_files(self, filename: str, expected_output: List[Problem]) -> None:
        apply_and_lint(filename, [Arg(Option.PYLINT, "--enable=long-function")], expected_output)

    @pytest.mark.parametrize(
        "filename,expected_output",
        [
            ("014422-next.py", [lazy_problem().set_line(19)]),
            ("023240-cards.py", []),
        ],
    )
    def test_use_early_return(self, filename: str, expected_output: List[Problem]) -> None:
        apply_and_lint(filename, [Arg(Option.PYLINT, "--enable=use-early-return")], expected_output)


@pytest.mark.parametrize(
    "filename,args,expected_output",
    [
        (
            "s2b8861_warehouse.py",
            [Arg(Option.IGNORE_INFILE_CONFIG_FOR, "flake8")],
            [
                lazy_problem().set_line(2).set_text("Forbidden magic comment 'noqa'"),
                lazy_problem().set_line(3).set_text("Forbidden magic comment 'noqa'"),
            ],
        ),
        (
            "s2b8861_warehouse.py",
            [Arg(Option.IGNORE_INFILE_CONFIG_FOR, "all")],
            [
                lazy_problem().set_line(2).set_text("Forbidden magic comment 'noqa'"),
                lazy_problem().set_line(3).set_text("Forbidden magic comment 'noqa'"),
            ],
        ),
        ("s2b8861_warehouse.py", [Arg(Option.IGNORE_INFILE_CONFIG_FOR, "pylint")], []),
        (
            "014422-next-early-return-disabled.py",
            [Arg(Option.PYLINT, "--enable=use-early-return")],
            [],
        ),
        (
            "014422-next-early-return-disabled.py",
            [
                Arg(Option.PYLINT, "--enable=use-early-return"),
                Arg(Option.IGNORE_INFILE_CONFIG_FOR, "pylint"),
            ],
            [lazy_problem().set_line(19).set_text("Forbidden magic comment 'pylint: disable'")],
        ),
        (
            "014422-next-early-return-disabled.py",
            [
                Arg(Option.PYLINT, "--enable=use-early-return"),
                Arg(Option.IGNORE_INFILE_CONFIG_FOR, "flake8"),
            ],
            [],
        ),
        (
            "014422-next-early-return-disabled.py",
            [
                Arg(Option.PYLINT, "--enable=use-early-return"),
                Arg(Option.IGNORE_INFILE_CONFIG_FOR, "all"),
            ],
            [lazy_problem().set_line(19).set_text("Forbidden magic comment 'pylint: disable'")],
        ),
    ],
)
def test_ignore_infile_config(
    filename: str, args: List[Arg], expected_output: List[Problem]
) -> None:
    apply_and_lint(filename, args, expected_output)


@pytest.mark.parametrize(
    "filename,args,expected_output",
    [
        (
            "umime_count_a.py",
            [
                Arg(Option.SET_GROUPS, "python-specific,enhancement"),
                Arg(Option.ALLOWED_ONECHAR_NAMES, ""),
            ],
            [
                lazy_problem()
                .set_code("C0104")
                .set_line(2)
                .set_text(
                    'Disallowed single-character variable name "a", choose a more descriptive name'
                ),
                lazy_problem().set_code("E225").set_line(2),
                lazy_problem()
                .set_code("R6101")
                .set_line(3)
                .set_text('Iterate directly: "for var in text" (with appropriate name for "var")'),
                lazy_problem().set_code("E225").set_line(4).set_column(19),
                lazy_problem().set_code("E225").set_line(4).set_column(35),
                lazy_problem()
                .set_code("R6609")
                .set_line(5)
                .set_text("Use augmented assignment: 'a += 1'"),
            ],
        ),
        (
            "umime_count_a_extended.py",
            [
                Arg(Option.SET_GROUPS, "python-specific,enhancement"),
                Arg(Option.ALLOWED_ONECHAR_NAMES, ""),
            ],
            [
                lazy_problem()
                .set_code("R6201")
                .set_line(2)
                .set_text("The if statement can be replaced with 'return ch == 'a' or ch == 'A''"),
                lazy_problem()
                .set_code("R1714")
                .set_line(2)
                .set_text("Consider merging these comparisons with 'in' by using 'ch in 'aA''"),
                lazy_problem()
                .set_code("C0104")
                .set_line(9)
                .set_text(
                    'Disallowed single-character variable name "a", choose a more descriptive name'
                ),
                lazy_problem()
                .set_code("R6101")
                .set_line(10)
                .set_text('Iterate directly: "for var in text" (with appropriate name for "var")'),
                lazy_problem()
                .set_code("R6609")
                .set_line(12)
                .set_text("Use augmented assignment: 'a += 1'"),
            ],
        ),
    ],
)
def test_umime_count_a(filename: str, args: List[Arg], expected_output: List[Problem]) -> None:
    apply_and_lint(filename, args, expected_output, from_empty=False)


@pytest.mark.parametrize(
    "lines,expected_output",
    [
        (["def fun():", "    return 42", "    pass"], [lazy_problem().set_code("W0101")]),
    ],
)
def test_overrides_custom(lines: List[str], expected_output: List[Problem]) -> None:
    create_apply_and_lint(lines, [Arg(Option.NO_FLAKE8, "on")], expected_output, from_empty=False)


@pytest.mark.parametrize("filename", ["hs3013-8548.py"])
def test_lints_without_error(filename: str) -> None:
    just_lint(filename, [], from_empty=False)


@pytest.mark.filterwarnings(
    "ignore:The 'default' argument to fields is deprecated. Use 'dump_default' instead."
)
def test_problem_can_be_dumped_to_json() -> None:
    problem = Problem(
        source=Linter.FLAKE8,
        enabled_by="foo",
        path="path",
        line=5,
        column=1,
        code="E303",
        text="too many blank lines (3)",
        end_line=None,
        end_column=None,
    )
    out = problem.to_json(indent=2, sort_keys=True)  # type: ignore
    assert (
        out
        == """{
  "code": "E303",
  "column": 1,
  "enabled_by": "foo",
  "end_column": null,
  "end_line": null,
  "line": 5,
  "path": "path",
  "source": "flake8",
  "symbol": null,
  "text": "too many blank lines (3)"
}"""
    )

    out = Problem.schema().dumps([problem], indent=2, many=True, sort_keys=True)  # type: ignore
    assert (
        out
        == """[
  {
    "code": "E303",
    "column": 1,
    "enabled_by": "foo",
    "end_column": null,
    "end_line": null,
    "line": 5,
    "path": "path",
    "source": "flake8",
    "symbol": null,
    "text": "too many blank lines (3)"
  }
]"""
    )
