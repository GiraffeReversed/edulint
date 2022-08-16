import pytest
from edulint.linters import Linters
from edulint.options import Option
from edulint.config.arg import Arg
from edulint.config.config import Config, apply_translates
from edulint.config.config_translates import get_config_translations
from edulint.linting.problem import Problem
from edulint.linting.linting import lint
from os.path import join
from typing import List

LAZY_INT = -1
FILLER_CODE = ""


def lazy_equals(received: Problem, expected: Problem) -> None:
    if expected.source:
        assert received.source == expected.source
    if expected.path:
        assert received.path == expected.path
    if expected.code is not None:
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


@pytest.mark.parametrize("filename,config,expected_output", [
    ("hello_world.py", Config(), []),
    ("z202817-zkouska.py", Config(), [lazy_problem().set_code("W0107").set_line(198)]),
    ("z202817-zkouska.py", Config(others={Linters.PYLINT: ["--enable=C0115"]}), [
        lazy_problem().set_code("C0115").set_line(124),
        lazy_problem().set_code("C0115").set_line(130),
        lazy_problem().set_code("W0107").set_line(198)
    ]),
    ("z202817-zkouska.py", Config(others={Linters.PYLINT: ["--enable=C0115", "--disable=W0107"]}), [
        lazy_problem().set_code("C0115").set_line(124),
        lazy_problem().set_code("C0115").set_line(130)
    ]),
    ("z202817-zkouska.py", Config(others={Linters.PYLINT: ["--disable=all"]}), []),
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


def apply_and_lint(filename: str, args: List[Arg], expected_output: List[Problem]) -> None:
    lazy_equal(
        lint(join("tests", "data", filename), apply_translates(args, get_config_translations())),
        expected_output
    )


@pytest.mark.parametrize("filename,args,expected_output", [
    ("z202817-zkouska.py", [Arg(Option.ENHANCEMENT)], [
        lazy_problem().set_code("W0107").set_line(198)
    ]),
    ("z202817-zkouska.py", [Arg(Option.PYTHON_SPEC)], [
        lazy_problem().set_code("C0200").set_line(82),
        lazy_problem().set_code("C0200").set_line(173),
        lazy_problem().set_code("C0123").set_line(174),
        lazy_problem().set_code("W0107").set_line(198),
    ]),
    ("z202817-zkouska.py", [Arg(Option.PYLINT, "--disable=all"), Arg(Option.PYTHON_SPEC)], [
        lazy_problem().set_code("C0200").set_line(82),
        lazy_problem().set_code("C0200").set_line(173),
        lazy_problem().set_code("C0123").set_line(174),
    ]),
])
def test_translations(filename: str, args: List[Arg], expected_output: List[Problem]) -> None:
    apply_and_lint(filename, args, expected_output)


@pytest.mark.parametrize("filename,args,expected_output", [
    ("014186-p2_nested.py", [Arg(Option.PYTHON_SPEC)], [
        lazy_problem().set_code("C0103").set_line(20),
        lazy_problem().set_code("C0103").set_line(21),
        lazy_problem().set_code("C0103").set_line(27),
        lazy_problem().set_code("C0103").set_line(28),
        lazy_problem().set_code("C0103").set_line(31),
        lazy_problem().set_code("C0103").set_line(34),
        lazy_problem().set_code("W0622").set_line(48),
    ]),
])
def test_invalid_name(filename: str, args: List[Arg], expected_output: List[Problem]) -> None:
    apply_and_lint(filename, args, expected_output)


@pytest.mark.parametrize("filename,args,expected_output", [
    ("014180-p5_fibsum.py", [Arg(Option.ALLOWED_ONECHAR_NAMES, "")], [
        lazy_problem().set_code("R6001").set_line(6),
        lazy_problem().set_code("R6001").set_line(14)
    ]),
    ("014180-p5_fibsum.py", [Arg(Option.ALLOWED_ONECHAR_NAMES, "n")], [
        lazy_problem().set_code("R6001").set_line(14)
    ]),
    ("014180-p5_fibsum.py", [Arg(Option.ALLOWED_ONECHAR_NAMES, "i")], [
        lazy_problem().set_code("R6001").set_line(6)
    ]),
    ("014180-p5_fibsum.py", [Arg(Option.ALLOWED_ONECHAR_NAMES, "in")], [
    ])
])
def test_allowed_onechar_names(filename: str, args: List[Arg], expected_output: List[Problem]) -> None:
    apply_and_lint(filename, args, expected_output)


@pytest.mark.parametrize("filename,args,expected_output", [
    ("105119-p5_template.py", [Arg(Option.PYTHON_SPEC), Arg(Option.PYLINT, "--disable=C0200")], [
        lazy_problem().set_code("R1714").set_line(22)
        .set_text("Consider merging these comparisons with \"in\" to \"i not in '[]'\""),
        lazy_problem().set_code("R1714").set_line(34)
        .set_text("Consider merging these comparisons with \"in\" to 'i in (1, 2, 3)'"),
    ]),
])
def test_consider_using_in(filename: str, args: List[Arg], expected_output: List[Problem]) -> None:
    apply_and_lint(filename, args, expected_output)


def test_problem_can_be_dumped_to_json() -> None:
    problem = Problem(source=Linters.FLAKE8, path='path', line=5, column=1, code='E303',
                      text='too many blank lines (3)', end_line=None, end_column=None)
    out = problem.to_json(indent=2)  # type: ignore
    assert out == """{
  "source": 2,
  "path": "path",
  "line": 5,
  "column": 1,
  "code": "E303",
  "text": "too many blank lines (3)",
  "end_line": null,
  "end_column": null
}"""
