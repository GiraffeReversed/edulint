from edulint.options import Option
from edulint.option_parses import get_option_parses
from edulint.config.arg import UnprocessedArg
from edulint.config.config import parse_config_file, Config
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


def remote_empty_config_url() -> str:
    return "https://raw.githubusercontent.com/GiraffeReversed/edulint/v2.9.2/edulint/config/files/empty.toml"


def prepare_config(args: List[UnprocessedArg], from_empty: bool) -> Config:
    config_args = Config("test", args)
    config_path = (
        config_args.get_last_value(Option.CONFIG_FILE, use_default=True)
        if not from_empty
        else "empty"
    )
    config_file_result = parse_config_file(config_path, get_option_parses())
    assert config_file_result is not None
    config_file, option_sets, _lang_translations = config_file_result
    return Config.combine(config_file, config_args).to_immutable(option_sets)


def just_lint(filename: str, args: List[UnprocessedArg], from_empty: bool = True) -> List[Problem]:
    config = prepare_config(args, from_empty)
    return lint_one(get_tests_path(filename), config)


def apply_and_lint(
    filename: str,
    args: List[UnprocessedArg],
    expected_output: List[Problem],
    from_empty: bool = True,
) -> None:
    lazy_equal(just_lint(filename, args, from_empty), expected_output)


def create_apply_and_lint(
    lines: List[str],
    args: List[UnprocessedArg],
    expected_output: List[Problem],
    from_empty: bool = True,
) -> None:
    tf = tempfile.NamedTemporaryFile("w+", delete=False)
    try:
        tf.writelines([line + "\n" for line in lines])
        tf.close()
        apply_and_lint(tf.name, args, expected_output, from_empty)
    finally:
        os.remove(tf.name)
