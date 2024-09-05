import pytest
from edulint.options import Option
from edulint.config.arg import Arg
from edulint.linting.problem import Problem
from test_utils import lazy_problem, apply_and_lint, create_apply_and_lint
from typing import List


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
def test_while_true_break(lines: List[str], expected_output: List[Problem]) -> None:
    create_apply_and_lint(
        lines,
        [Arg(Option.PYLINT, "--enable=no-while-true")],
        [p.set_code("R6301") for p in expected_output]
    )


@pytest.mark.parametrize("lines,expected_output", [
    ([
        "n = 10",
        "i = 0",
        "while i < n:",
        "    print('foo' + str(i))",
        "    i += 1",
    ], [lazy_problem().set_line(3)]),
])
def test_use_for_loop_custom(lines: List[str], expected_output: List[Problem]) -> None:
    create_apply_and_lint(
        lines,
        [Arg(Option.PYLINT, "--enable=use-for-loop")],
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
    ([
        "for _ in range(10):",
        "    _ = 'a,b,c,d'.split(',', 1)",
    ], [
    ]),
    ([
        "for _ in range(10):",
        "    _, rest = 'a,b,c,d'.split(',', 1)",
    ], [
    ]),
    ([
        "for _ in range(10):",
        "    for _ in range(10):"
        "        _, rest = 'a,b,c,d'.split(',', 1)",
    ], [
    ])
])
def test_changing_control_variable_custom(lines: List[str], expected_output: List[Problem]) -> None:
    create_apply_and_lint(
        lines,
        [Arg(Option.PYLINT, "--enable=changing-control-variable")],
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
def test_tighter_bounds_files(filename: str, expected_output: List[Problem]) -> None:
    apply_and_lint(
        filename,
        [Arg(Option.PYLINT, "--enable=use-tighter-boundaries")],
        expected_output
    )


@pytest.mark.parametrize("filename,expected_output", [
    ("010666-even.py", [lazy_problem().set_line(9)]),
    ("012630-next.py", []),
    ("012986-nested.py", [lazy_problem().set_line(35)]),
    ("013450-next.py", []),
    ("014286-coins.py", []),
    ("014556-prime.py", [lazy_problem().set_line(13)]),
    ("014962-sequence.py", [lazy_problem().set_line(18)]),
    ("015794-amicable.py", [lazy_problem().set_line(14)]),
    ("016119-coins.py", [lazy_problem().set_line(22)]),
    ("017667-coins.py", []),
    ("023140-credit.py", []),
    ("043611-swap_columns.py", []),
    ("05ad83ee13-p5_credit.py", []),
    ("064fe05979.py", []),
    ("11fa2efd2c-exam1.py", []),  # would force using for control after loop
    ("3949eabe39-hw3.py", []),
    ("5ac87a0e60-hw3.py", [lazy_problem().set_line(152), lazy_problem().set_line(164)]),
    ("62398f5c25.py", [lazy_problem().set_line(111)]),
    ("b2c113956e-d_mancala.py", [lazy_problem().set_line(31)]),
    ("f56a8957e2-p3_triples.py", []),
    ("uc_1597_09_16.py", []),
    ("uc_3776_30_15.py", []),
    ("uc_7004_17_14.py", [lazy_problem().set_line(3)]),
])
def test_use_for_loop_files(filename: str, expected_output: List[Problem]) -> None:
    apply_and_lint(
        filename,
        [Arg(Option.PYLINT, "--enable=use-for-loop")],
        [problem.set_code("R6305") for problem in expected_output]
    )


# OBJ_DEF = [
#     "class Obj:",
#     "    def __init__(self):",
#     "        self.elems = []",
# ]

# @pytest.mark.parametrize("lines,expected_output", [
#     (OBJ_DEF + [
#         "obj = Obj()",
#         "for v in obj.elems:",
#         "    obj.elems.append('x')",
#     ], [lazy_problem().set_line(6)]),
#     (OBJ_DEF + [
#         "obj = Obj()",
#         "for v in obj.elems:",
#         "    obj = Obj()",
#         "    obj.elems.append('y')"
#     ], []),
#     (OBJ_DEF + [
#         "obj = Obj()",
#         "for v in obj.elems:",
#         "    obj.elems = []",
#     ], [lazy_problem().set_line(6)]),
#     (OBJ_DEF + [
#         "obj = Obj()",
#         "for v in obj.elems:",
#         "    obj.elems.append('x')",
#         "    obj = Obj()",
#         "    obj.elems.append('y')"
#     ], [lazy_problem().set_line(6)]),
# ])
# def test_modifying_iterated_custom(lines: List[str], expected_output: List[Problem]) -> None:
#     create_apply_and_lint(
#         lines,
#         [Arg(Option.PYLINT, "--enable=modifying-iterated-structure")],
#         [problem.set_code("R6303") for problem in expected_output]
#     )

@pytest.mark.parametrize("filename,expected_output", [
    ("034636-right_cellular.py", []),
    ("104526-subset_sum.py", [
        lazy_problem().set_line(17)
        .set_text("Iterated structure nums is being modified inside the for loop body. "
                  "Use while loop or iterate over a copy."),
        lazy_problem().set_line(22)
    ]),
    ("035794-partition.py", []),
    ("2902f19359.py", []),
    ("eba554ae42-HW4.py", [lazy_problem().set_line(189)]),
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
def test_modifying_iterated_files(filename: str, expected_output: List[Problem]) -> None:
    apply_and_lint(
        filename,
        [Arg(Option.PYLINT, "--enable=modifying-iterated-structure")],
        [problem.set_code("R6303") for problem in expected_output]
    )


@pytest.mark.parametrize("filename,expected_output", [
    ("hw33176.py", []),
    ("m4521.py", [
        lazy_problem().set_line(117).set_text("Inner for loop shadows outer for loop's control variable i.")
    ])
])
def test_shadowed_control_var_files(filename: str, expected_output: List[Problem]) -> None:
    apply_and_lint(
        filename,
        [Arg(Option.PYLINT, "--enable=loop-shadows-control-variable")],
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
def test_changing_control_var_files(filename: str, expected_output: List[Problem]) -> None:
    apply_and_lint(
        filename,
        [Arg(Option.PYLINT, "--enable=changing-control-variable")],
        [problem.set_code("R6304") for problem in expected_output]
    )


@pytest.mark.parametrize("lines,expected_output", [
    ([
        "A = list(range(10))",
        "B = []",
        "for x in range(len(A)):",
        "    for y in range(len(A)):",
        "        B.append(A[x])",
        "        B.append(y)",
    ], [
        lazy_problem().set_line(3)
        .set_text('Iterate directly: "for var in A" (with appropriate name for "var")'),
    ]),
    ([
        "A = list(range(10))",
        "for i in range(5, len(A)):",
        "    print(A[i])"
    ], []),
    ([
        "A = list(range(10))",
        "a = 5",
        "for i in range(a, len(A)):",
        "    print(A[i])"
    ], []),
    ([
        "A = list(range(10))",
        "a = 5",
        "for i in range(a, len(A)):",
        "    print(i, A[i])",
    ], []),
    ([
        "A = list(range(10))",
        "B = []",
        "for x in range(len(A)):",
        "    x += 1",
        "    B.append(A[x])",
        "    B.append(A[x + 1])",
    ], []),
    ([
        "A = list(range(10))",
        "B = []",
        "for x in range(len(A)):",
        "    B.append(A[x + 1])",
    ], []),
    ([
        "A = list(range(10))",
        "for x in range(len(A)):",
        "    A[x] = A[x] + 1"
    ], []),
    ([
        "A = list(range(10))",
        "B = []",
        "for x in range(len(A)):",
        "    for x in range(len(B)):",
        "        B.append(A[x])",
    ], []),
])
def test_use_foreach_custom(lines: List[str], expected_output: List[Problem]) -> None:
    create_apply_and_lint(
        lines, [Arg(Option.PYLINT, "--enable=use-foreach")], expected_output
    )

@pytest.mark.parametrize("filename,expected_output", [
    ("00bcea235f.py", [lazy_problem().set_line(23)]),
    ("014771-p2_nested.py", [
            lazy_problem().set_line(25)
            .set_text('Iterate directly: "for var in A" (with appropriate name for "var")'),
            lazy_problem().set_line(35)
            .set_text('Iterate directly: "for var in A" (with appropriate name for "var")'),
    ]),
    ("015080-p4_geometry.py", []),
    ("01c9f86c74-task_2.py", []),
    ("03-d4_points.py", []),
    ("045294-p4_vigenere.py", []),
    ("046542-polybius.py", [lazy_problem().set_line(67)]),
    ("05784ba6f8.py", [lazy_problem().set_line(46)]),
    ("105119-p5_template.py", []),
    ("35a73a1aa0.py", []),
    ("5e3d9ea337-greater.py", []),
    ("b313a82293.py", [
        lazy_problem().set_line(25),
        lazy_problem().set_line(26),
        lazy_problem().set_line(33),
    ]),
    ("be217c2c64-midterm_alt.py", []),
    ("d9f34aa130-fixpoint.py", [lazy_problem().set_line(31)]),
    ("umime_count_a.py", [
        lazy_problem().set_line(3)
        .set_text('Iterate directly: "for var in text" (with appropriate name for "var")'),
    ]),
])
def test_use_foreach(filename: str, expected_output: List[Problem]):
    apply_and_lint(filename, [Arg(Option.PYLINT, "--enable=use-foreach")], expected_output)


@pytest.mark.parametrize("lines,expected_output", [
    ([
        "A = list(range(10))",
        "B = []",
        "for x in range(len(A)):",
        "    for y in range(len(A)):",
        "        B.append(A[x])",
        "        B.append(y)",
    ], []),
    ([
        "A = list(range(10))",
        "for i in range(5, len(A)):",
        "    print(A[i])"
    ], []),
    ([
        "A = list(range(10))",
        "a = 5",
        "for i in range(a, len(A)):",
        "    print(A[i])"
    ], []),
    ([
        "A = list(range(10))",
        "a = 5",
        "for i in range(a, len(A)):",
        "    print(i, A[i])",
    ], []),
    ([
        "A = list(range(10))",
        "B = []",
        "for x in range(len(A)):",
        "    x += 1",
        "    B.append(A[x])",
        "    B.append(A[x + 1])",
    ], []),
    ([
        "A = list(range(10))",
        "B = []",
        "for x in range(len(A)):",
        "    B.append(A[x + 1])",
    ], []),
    ([
        "A = list(range(10))",
        "for x in range(len(A)):",
        "    A[x] = A[x] + 1"
    ], [  # unnecessary?
            # lazy_problem()
            # .set_line(2)
            # .set_text(
            #     'Iterate using enumerate: "for x, var in enumerate(A)" (with appropriate name for "var")'
            # ),
    ]),
    ([
        "A = list(range(10))",
        "for x in range(len(A)):",
        "    print(x, A[x])"
    ], [
        lazy_problem().set_line(2)
        .set_text('Iterate using enumerate: "for x, var in enumerate(A)" (with appropriate name for "var")'),
    ]),
    ([
        "A = list(range(10))",
        "B = []",
        "for x in range(len(A)):",
        "    for x in range(len(B)):",
        "        B.append(A[x])",
    ], [])
])
def test_use_enumerate_custom(lines: List[str], expected_output: List[Problem]) -> None:
    create_apply_and_lint(
        lines, [Arg(Option.PYLINT, "--enable=use-enumerate")], expected_output
    )

@pytest.mark.parametrize("filename,expected_output", [
    ("014771-p2_nested.py", []),
    ("015080-p4_geometry.py", []),
    ("01c9f86c74-task_2.py", []),
    ("03-d4_points.py", []),
    ("041378925b-f_tetris.py", [lazy_problem().set_line(134), lazy_problem().set_line(135)]),
    ("045294-p4_vigenere.py", []),
    ("046542-polybius.py", [
        lazy_problem().set_line(44),
        lazy_problem().set_line(45),
        lazy_problem().set_line(46),  # multi-step
        lazy_problem().set_line(68),
        lazy_problem().set_line(69),  # multi-step
    ]),
    ("105119-p5_template.py", []),
    ("35a73a1aa0.py", []),
    ("7097dd29de-p1_lists.py", [lazy_problem().set_line(46)]),
    ("be217c2c64-midterm_alt.py", []),
    ("d9f34aa130-fixpoint.py", []),
    ("umime_count_a.py", []),
])
def test_use_enumerate(filename: str, expected_output: List[Problem]):
    apply_and_lint(filename, [Arg(Option.PYLINT, "--enable=use-enumerate")], expected_output)
