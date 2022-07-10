import pytest
from edulint import lint, Problem, Arg, Config, Linters, apply_translates, CONFIG_TRANSLATES
from os.path import join
from typing import List

LAZY_INT = -1
FILLER_CODE = "FILLER"


def lazy_equals(received: Problem, expected: Problem) -> None:
    if expected.source:
        assert received.source == expected.source
    if expected.path:
        assert received.path == expected.path
    if expected.code:
        assert received.code == expected.code
    if expected.line != LAZY_INT:
        assert received.line == expected.line
    if expected.column != LAZY_INT:
        assert received.column == expected.column
    if expected.text:
        assert received.text == expected.text
    if expected.end_line != LAZY_INT:
        assert received.end_line == expected.end_line
    if expected.end_column != LAZY_INT:
        assert received.end_column == expected.end_column


def lazy_problem() -> Problem:
    return Problem("", "", LAZY_INT, LAZY_INT, "", "", LAZY_INT, LAZY_INT)


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


@pytest.mark.parametrize("filename,config,expected_output", [
    ("hello_world.py", Config(), []),
    ("z202817-zkouska.py", Config(), [lazy_problem().set_code("W0107").set_line(198)]),
    ("z202817-zkouska.py", Config({Linters.PYLINT: ["--enable=C0115"]}), [
        lazy_problem().set_code("C0115").set_line(124),
        lazy_problem().set_code("C0115").set_line(130),
        lazy_problem().set_code("W0107").set_line(198)
    ]),
    ("z202817-zkouska.py", Config({Linters.PYLINT: ["--enable=C0115", "--disable=W0107"]}), [
        lazy_problem().set_code("C0115").set_line(124),
        lazy_problem().set_code("C0115").set_line(130)
    ]),
    ("z202817-zkouska.py", Config({Linters.PYLINT: ["--disable=all"]}), []),
    ("002814-p1_trapezoid.py", Config(), [
        lazy_problem().set_code("F401").set_line(1),
        lazy_problem().set_code("F401").set_line(1),
        lazy_problem().set_code("E501").set_line(1),
        lazy_problem().set_code("W293").set_line(19),
        lazy_problem().set_code("E303").set_line(22),
    ])
])
def test_lint(filename: str, config: Config, expected_output: List[Problem]) -> None:
    lazy_equal(lint(join("tests", "data", filename), config), expected_output)


@pytest.mark.parametrize("filename,args,expected_output", [
    ("z202817-zkouska.py", [Arg(Linters.EDULINT, "enhancement")], [
        lazy_problem().set_code("W0107").set_line(198)
    ]),
    ("z202817-zkouska.py", [Arg(Linters.EDULINT, "python_spec")], [
        lazy_problem().set_code("C0200").set_line(82),
        lazy_problem().set_code("C0200").set_line(173),
        lazy_problem().set_code("C0123").set_line(174),
        lazy_problem().set_code("W0107").set_line(198),
    ]),
    ("z202817-zkouska.py", [Arg(Linters.PYLINT, "--disable=all"), Arg(Linters.EDULINT, "python_spec")], [
        lazy_problem().set_code("C0200").set_line(82),
        lazy_problem().set_code("C0200").set_line(173),
        lazy_problem().set_code("C0123").set_line(174),
    ]),
    ("014186-p2_nested.py", [Arg(Linters.EDULINT, "python_spec")], [
        lazy_problem().set_code("C0103").set_line(20),
        lazy_problem().set_code("C0103").set_line(21),
        lazy_problem().set_code("C0103").set_line(27),
        lazy_problem().set_code("C0103").set_line(28),
        lazy_problem().set_code("C0103").set_line(31),
        lazy_problem().set_code("C0103").set_line(34),
        lazy_problem().set_code("W0622").set_line(48),
    ]),
])
def test_apply_and_lint(filename: str, args: Arg, expected_output: List[Problem]) -> None:
    lazy_equal(lint(join("tests", "data", filename), apply_translates(args, CONFIG_TRANSLATES)), expected_output)
