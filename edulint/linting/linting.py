from typing import List, Callable, Tuple, Dict, Set, Any
from edulint.linting.problem import ProblemJson, Problem
from edulint.linting.nonparsing_checkers import report_infile_config
from edulint.linting.process_handler import ProcessHandler
from edulint.linting.overrides import get_overriders
from edulint.linting.tweakers import get_tweakers, Tweakers
from edulint.config.config import ImmutableConfig
from edulint.config.language_translations import LangTranslations
from edulint.options import Option, ImmutableT
from edulint.linters import Linter
from functools import partial
import sys
import json
import os
from pathlib import Path
from loguru import logger


class EduLintLinterFailedException(Exception):
    pass


def get_proper_path(path: str) -> str:
    return os.path.abspath(path) if os.path.isabs(path) else os.path.relpath(path)


def flake8_to_problem(enablers: Dict[str, str], raw: ProblemJson) -> Problem:
    assert isinstance(raw["filename"], str), f'got {type(raw["filename"])} for filename'
    assert isinstance(raw["line_number"], int), f'got {type(raw["line_number"])} for line_number'
    assert isinstance(
        raw["column_number"], int
    ), f'got {type(raw["column_number"])} for column_number'
    assert isinstance(raw["code"], str), f'got {type(raw["code"])} for code'
    assert isinstance(raw["text"], str), f'got {type(raw["text"])} for text'

    return Problem(
        Linter.FLAKE8,
        enablers.get(raw["code"]),
        get_proper_path(raw["filename"]),
        raw["line_number"],
        raw["column_number"],
        raw["code"],
        raw["text"],
    )


def pylint_to_problem(
    files_or_dirs: List[str], enablers: Dict[str, str], raw: ProblemJson
) -> Problem:
    assert isinstance(raw["path"], str), f'got {type(raw["path"])} for path'
    assert isinstance(raw["line"], int), f'got {type(raw["line"])} for line'
    assert isinstance(raw["column"], int), f'got {type(raw["column"])} for column'
    assert isinstance(raw["message-id"], str), f'got {type(raw["message-id"])} for message-id'
    assert isinstance(raw["message"], str), f'got {type(raw["message"])} for message'
    assert (
        isinstance(raw["endLine"], int) or raw["endLine"] is None
    ), f'got {type(raw["endLine"])} for endLine'
    assert (
        isinstance(raw["endColumn"], int) or raw["endColumn"] is None
    ), f'got {type(raw["endColumn"])} for endColumn'
    assert isinstance(raw["symbol"], str), f'get {type(raw["symbol"])} for symbol'

    def get_used_filename(path: str) -> str:
        path = Path(path)
        for fd in [Path(path) for path in files_or_dirs]:
            abs_path = path.absolute()
            abs_fd = fd.absolute()
            if abs_fd == abs_path or abs_fd in abs_path.parents:
                if fd.is_absolute():
                    return path.absolute()
                else:
                    return fd / path.relative_to(fd)
        assert False, "unreachable"

    code_enabler = enablers.get(raw["message-id"])
    symbol_enabler = enablers.get(raw["symbol"])

    return Problem(
        Linter.PYLINT,
        code_enabler if code_enabler is not None else symbol_enabler,
        get_proper_path(get_used_filename(raw["path"])),
        raw["line"],
        raw["column"],
        raw["message-id"],
        raw["message"],
        raw["endLine"],
        raw["endColumn"],
        raw["symbol"],
    )


def lint_any(
    linter: Linter,
    files_or_dirs: List[str],
    linter_args: List[str],
    config_arg: ImmutableT,
    result_getter: Callable[[Any], Any],
    out_to_problem: Callable[[Dict[str, str], ProblemJson], Problem],
    enablers: Dict[str, str],
) -> List[Problem]:
    command = [sys.executable, "-m", str(linter)] + linter_args + list(config_arg) + files_or_dirs  # type: ignore
    return_code, outs, errs = ProcessHandler.run(command, timeout=1000)

    if ProcessHandler.is_status_code_by_timeout(return_code):
        logger.critical("{linter} was likely killed by timeout", linter=linter)
        raise TimeoutError(f"Timeout from {linter}")

    errs = errs.strip()
    if errs:
        logger.error(errs)

    if (linter == Linter.FLAKE8 and return_code not in (0, 1)) or (
        linter == Linter.PYLINT and return_code == 32
    ):
        logger.critical(
            "{linter} exited with {return_code}", linter=linter, return_code=return_code
        )
        raise EduLintLinterFailedException()

    if not outs:
        return []

    try:
        parsed = json.loads(outs)
    except json.decoder.JSONDecodeError as e:
        logger.critical("could not parse results:\n{e}", e=e)
        logger.debug(outs)
        raise e

    return list(map(partial(out_to_problem, enablers), result_getter(parsed)))


def lint_edulint(files_or_dirs: List[str], config: ImmutableConfig) -> List[Problem]:
    ignored_infile = set(config[Option.IGNORE_INFILE_CONFIG_FOR])
    if len(ignored_infile) > 0:
        return report_infile_config(files_or_dirs, ignored_infile, config.enablers)
    return []


def lint_flake8(files_or_dirs: List[str], config: ImmutableConfig) -> List[Problem]:
    flake8_args = ["--format=json"]
    return lint_any(
        Linter.FLAKE8,
        files_or_dirs,
        flake8_args,
        config[Option.FLAKE8],
        lambda r: [problem for problems in r.values() for problem in problems],
        flake8_to_problem,
        config.enablers,
    )


def lint_pylint(files_or_dirs: List[str], config: ImmutableConfig) -> List[Problem]:
    pylint_args = ["--output-format=json", "--recursive=y"]

    return lint_any(
        Linter.PYLINT,
        files_or_dirs,
        pylint_args,
        config[Option.PYLINT],
        lambda r: r,
        partial(pylint_to_problem, files_or_dirs),
        config.enablers,
    )


def apply_overrides(problems: List[Problem], overriders: Dict[str, Set[str]]) -> List[Problem]:
    codes_on_lines: Dict[int, Set[str]] = {
        line: set() for line in set([problem.line for problem in problems])
    }

    for problem in problems:
        codes_on_lines[problem.line].add(problem.code)

    result = []
    for problem in problems:
        o = overriders.get(problem.code, set())
        if not (o & codes_on_lines[problem.line]):
            result.append(problem)

    return result


def apply_tweaks(
    problems: List[Problem], tweakers: Tweakers, config: ImmutableConfig
) -> List[Problem]:
    result = []
    for problem in problems:
        tweaker = tweakers.get((problem.source, problem.code))
        if tweaker:
            if tweaker.should_keep(
                problem, [arg for arg in config if arg.option in tweaker.used_options]
            ):
                problem.text = tweaker.get_reword(problem)
                result.append(problem)
        else:
            result.append(problem)
    return result


def lint_one(filename: str, config: Tuple[ImmutableConfig, LangTranslations]) -> List[Problem]:
    option_config, lang_translations = config
    return lint_many([([filename], option_config, lang_translations)])


def sort(files_or_dirs: List[str], problems: List[Problem]) -> List[Problem]:
    files_or_dirs = [Path(path) for path in files_or_dirs]

    def get_file_or_dir_index(path: str):
        path = Path(path)
        for i, fd in enumerate(files_or_dirs):
            if fd == path or fd in path.parents:
                return i
        assert False, "unreachable"

    problems.sort(
        key=lambda problem: (
            get_file_or_dir_index(problem.path),
            problem.path,
            problem.line,
            problem.column,
        )
    )
    return problems


def lint(files_or_dirs: List[str], config: ImmutableConfig) -> List[Problem]:
    logger.info("linting files: {files_or_dirs}", files_or_dirs=files_or_dirs)
    logger.info("using config: {config}", config=config)

    edulint_result = lint_edulint(files_or_dirs, config)
    flake8_result = [] if config[Option.NO_FLAKE8] else lint_flake8(files_or_dirs, config)
    pylint_result = lint_pylint(files_or_dirs, config)

    result = apply_overrides(edulint_result + flake8_result + pylint_result, get_overriders())
    result = apply_tweaks(result, get_tweakers(), config)
    return sort(files_or_dirs, result)


def translate(lang_translations: LangTranslations, problem: Problem):
    translation = lang_translations.get(problem.code)
    if translation is None:
        translation = lang_translations.get(problem.symbol)
        if translation is None:
            return problem

    problem.text = translation.translate(problem.code, problem.text)
    return problem


def lint_many(
    partition: List[Tuple[List[str], ImmutableConfig, LangTranslations]]
) -> List[Problem]:
    return [
        translate(lang_translations, problem)
        for files_or_dirs, config, lang_translations in partition
        for problem in lint(files_or_dirs, config)
    ]
