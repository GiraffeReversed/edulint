from edulint.options import Option, DEFAULT_CONFIG
from edulint.option_parses import get_option_parses
from edulint.config.arg import Arg
from edulint.config.config import parse_config_file, convert, combine_and_translate, Config
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


def apply_and_lint(
    filename: str, args: List[Arg], expected_output: List[Problem], from_empty: bool = True
) -> None:
    def get_config_path(args: List[Arg]) -> str:
        for arg in reversed(args):
            if arg.option == Option.CONFIG:
                return arg.val
        return DEFAULT_CONFIG if not from_empty else "empty"

    def get_config_file(args: List[Arg]) -> List[Arg]:
        config_path = get_config_path(args)
        config = parse_config_file(
            config_path, get_option_parses(), get_config_translations(), get_ib111_translations()
        )
        assert config is not None
        return config

    config_file = get_config_file(args)
    converted_args = convert(args, get_option_parses())
    config = Config(
        combine_and_translate(
            config_file + converted_args,
            get_option_parses(),
            get_config_translations(),
            get_ib111_translations(),
        )
    )
    lazy_equal(
        lint_one(get_tests_path(filename), config),
        expected_output,
    )


def create_apply_and_lint(
    lines: List[str], args: List[Arg], expected_output: List[Problem], from_empty: bool = True
) -> None:
    tf = tempfile.NamedTemporaryFile("w+", delete=False)
    try:
        tf.writelines([line + "\n" for line in lines])
        tf.close()
        apply_and_lint(tf.name, args, expected_output, from_empty)
    finally:
        os.remove(tf.name)
