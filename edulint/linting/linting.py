from typing import List, Callable, Any
from edulint.linting.problem import ProblemJson, Problem
from edulint.linting.process_handler import ProcessHandler
from edulint.linting.tweakers import get_tweakers, Tweakers
from edulint.config.config import Config
from edulint.linters import Linters
import sys
import json
import pathlib


def flake8_to_problem(raw: ProblemJson) -> Problem:
    assert isinstance(raw["filename"], str), f'got {type(raw["filename"])} for filename'
    assert isinstance(raw["line_number"], int), f'got {type(raw["line_number"])} for line_number'
    assert isinstance(raw["column_number"], int), f'got {type(raw["column_number"])} for column_number'
    assert isinstance(raw["code"], str), f'got {type(raw["code"])} for code'
    assert isinstance(raw["text"], str), f'got {type(raw["text"])} for text'

    return Problem(
        Linters.FLAKE8,
        raw["filename"],
        raw["line_number"],
        raw["column_number"],
        raw["code"],
        raw["text"]
    )


def pylint_to_problem(raw: ProblemJson) -> Problem:
    assert isinstance(raw["path"], str), f'got {type(raw["path"])} for path'
    assert isinstance(raw["line"], int), f'got {type(raw["line"])} for line'
    assert isinstance(raw["column"], int), f'got {type(raw["column"])} for column'
    assert isinstance(raw["message-id"], str), f'got {type(raw["message-id"])} for message-id'
    assert isinstance(raw["message"], str), f'got {type(raw["message"])} for message'
    assert isinstance(raw["endLine"], int) or raw["endLine"] is None, f'got {type(raw["endLine"])} for endLine'
    assert isinstance(raw["endColumn"], int) or raw["endColumn"] is None, f'got {type(raw["endColumn"])} for endColumn'

    return Problem(
        Linters.PYLINT,
        raw["path"],
        raw["line"],
        raw["column"],
        raw["message-id"],
        raw["message"],
        raw["endLine"],
        raw["endColumn"]
    )


def lint_any(
        linter: Linters, filename: str, args: List[str], config: List[str],
        result_getter: Callable[[Any], Any],
        out_to_problem: Callable[[ProblemJson], Problem]) -> List[Problem]:
    command = [sys.executable, "-m", str(linter)] + args + config + [filename]
    return_code, outs, errs = ProcessHandler.run(command, timeout=10)
    if (linter == Linters.FLAKE8 and return_code not in (0, 1)) or (linter == Linters.PYLINT and return_code == 32):
        print(errs, file=sys.stderr, end="")
        print(f"edulint: {command[2]} exited with {return_code}", file=sys.stderr)
        exit(return_code)
    if not outs:
        return []
    result = result_getter(json.loads(outs))
    return list(map(out_to_problem, result))


def lint_flake8(filename: str, config: Config) -> List[Problem]:
    flake8_args = ["--format=json"]
    return lint_any(
        Linters.FLAKE8, filename, flake8_args, config.config[Linters.FLAKE8],
        lambda r: r[filename],
        flake8_to_problem)


def lint_pylint(filename: str, config: Config) -> List[Problem]:
    cwd = pathlib.Path(__file__).parent.resolve()
    pylint_args = [f'--rcfile={cwd}/.pylintrc', "--output-format=json"]
    return lint_any(
        Linters.PYLINT, filename, pylint_args, config.config[Linters.PYLINT],
        lambda r: r, pylint_to_problem)


def apply_tweaks(problems: List[Problem], tweakers: Tweakers) -> List[Problem]:
    result = []
    for problem in problems:
        tweaker = tweakers.get((problem.source, problem.code))
        if tweaker:
            if tweaker.should_keep(problem):
                problem.text = tweaker.get_reword(problem)
                result.append(problem)
        else:
            result.append(problem)
    return result


def lint(filename: str, config: Config) -> List[Problem]:
    result = lint_flake8(filename, config) + lint_pylint(filename, config)
    result = apply_tweaks(result, get_tweakers())
    result.sort(key=lambda problem: (problem.line, problem.column))
    return result
