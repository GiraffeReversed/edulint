from edulint.options import Option
from edulint.config.arg import UnprocessedArg
from edulint.config.config import Config, get_config_many
from edulint.linting.problem import Problem
from edulint.linting.linting import lint_many
from dataclasses import fields, replace
import os
import pathlib
from typing import List

import tempfile
from loguru import logger

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


def prepare_configs(paths: List[str], args: List[UnprocessedArg], from_empty: bool) -> Config:
    if from_empty:
        args = [UnprocessedArg(Option.CONFIG_FILE, "empty")] + args
    partition = get_config_many(
        paths,
        [f"{arg.option.to_name()}={arg.val}" if arg.val is not None else arg.option.to_name() for arg in args]
    )
    assert len(partition) > 0
    return partition


def just_lint(filenames: List[str], args: List[UnprocessedArg], from_empty: bool = True) -> List[Problem]:
    paths = [get_tests_path(fn) for fn in filenames]
    partition = prepare_configs(paths, args, from_empty)
    return lint_many(partition)


def apply_and_lint(
    filename: str,
    args: List[UnprocessedArg],
    expected_output: List[Problem],
    from_empty: bool = True,
) -> None:
    apply_and_lint_multiple([filename], args, expected_output, from_empty)


def apply_and_lint_multiple(
    filenames: List[str],
    args: List[UnprocessedArg],
    expected_output: List[Problem],
    from_empty: bool=True,
) -> None:

    def stderr_reporter(m):
        nonlocal fail
        fail = True

    fail = False
    logger.add(stderr_reporter, level="ERROR")

    lazy_equal(just_lint(filenames, args, from_empty), expected_output)

    if fail:
        assert False, "error in stderr"

def create_apply_and_lint(
    lines: List[str],
    args: List[UnprocessedArg],
    expected_output: List[Problem],
    from_empty: bool = True,
) -> None:
    tf = tempfile.NamedTemporaryFile("w+", delete=False, suffix=".py")
    try:
        tf.writelines([line + "\n" for line in lines])
        tf.close()
        apply_and_lint(tf.name, args, expected_output, from_empty)
    finally:
        os.remove(tf.name)
