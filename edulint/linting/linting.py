from typing import List, Callable, Tuple, Dict, Set, Any
from edulint.config.arg import ImmutableArg
from edulint.linting.problem import ProblemJson, Problem
from edulint.linting.process_handler import ProcessHandler
from edulint.linting.overrides import get_overriders
from edulint.linting.tweakers import get_tweakers, Tweakers
from edulint.config.config import Config
from edulint.options import Option
from edulint.linters import Linter
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
        Linter.FLAKE8,
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
        Linter.PYLINT,
        raw["path"],
        raw["line"],
        raw["column"],
        raw["message-id"],
        raw["message"],
        raw["endLine"],
        raw["endColumn"]
    )


def lint_any(
        linter: Linter, filenames: List[str], linter_args: List[str], config_arg: ImmutableArg,
        result_getter: Callable[[Any], Any],
        out_to_problem: Callable[[ProblemJson], Problem]) -> List[Problem]:
    command = [sys.executable, "-m", str(linter)] + linter_args + list(config_arg.val) + filenames  # type: ignore
    return_code, outs, errs = ProcessHandler.run(command, timeout=10)

    print(errs, file=sys.stderr, end="")
    if (linter == Linter.FLAKE8 and return_code not in (0, 1)) or (linter == Linter.PYLINT and return_code == 32):
        print(f"edulint: {linter} exited with {return_code}", file=sys.stderr)
        exit(return_code)

    if not outs:
        return []

    result = result_getter(json.loads(outs))
    return list(map(out_to_problem, result))


def lint_flake8(filenames: List[str], config: Config) -> List[Problem]:
    flake8_args = ["--format=json"]
    return lint_any(
        Linter.FLAKE8, filenames, flake8_args, config[Option.FLAKE8],
        lambda r: [problem for problems in r.values() for problem in problems],
        flake8_to_problem)


def lint_pylint(filenames: List[str], config: Config) -> List[Problem]:
    cwd = pathlib.Path(__file__).parent.resolve()
    pylint_args = [f'--rcfile={cwd}/.pylintrc', "--output-format=json"]
    return lint_any(
        Linter.PYLINT, filenames, pylint_args, config[Option.PYLINT],
        lambda r: r, pylint_to_problem)


def apply_overrides(problems: List[Problem], overriders: Dict[str, Set[str]]) -> List[Problem]:
    codes_on_lines: Dict[int, Set[str]] = {line: set() for line in set([problem.line for problem in problems])}

    for problem in problems:
        codes_on_lines[problem.line].add(problem.code)

    result = []
    for problem in problems:
        o = overriders.get(problem.code, set())
        if not (o & codes_on_lines[problem.line]):
            result.append(problem)

    return result


def apply_tweaks(problems: List[Problem], tweakers: Tweakers, config: Config) -> List[Problem]:
    result = []
    for problem in problems:
        tweaker = tweakers.get((problem.source, problem.code))
        if tweaker:
            if tweaker.should_keep(problem, [arg for arg in config if arg.option in tweaker.used_options]):
                problem.text = tweaker.get_reword(problem)
                result.append(problem)
        else:
            result.append(problem)
    return result


def lint_one(filename: str, config: Config) -> List[Problem]:
    return lint([filename], config)


def sort(filenames: List[str], problems: List[Problem]) -> List[Problem]:
    indices = {fn: i for i, fn in enumerate(filenames)}
    problems.sort(key=lambda problem: (indices[problem.path], problem.line, problem.column))
    return problems


def lint(filenames: List[str], config: Config) -> List[Problem]:
    result = lint_flake8(filenames, config) + lint_pylint(filenames, config)
    result = apply_overrides(result, get_overriders())
    result = apply_tweaks(result, get_tweakers(), config)
    return sort(filenames, result)


def lint_many(partition: List[Tuple[List[str], Config]]) -> List[Problem]:
    return [problem for filenames, config in partition for problem in lint(filenames, config)]
