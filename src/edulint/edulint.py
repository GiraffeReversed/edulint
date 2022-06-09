#!/usr/bin/python3

from typing import List, Dict, Union, Optional
from edulint.process_handler import ProcessHandler
from edulint.explanations import explanations
import argparse
import json
from dataclasses import dataclass, asdict
import pathlib
import sys
# import time


ProblemJson = Dict[str, Union[str, int]]


@dataclass
class Problem:
    source: str
    path: str
    line: int
    column: int
    code: str
    text: str
    end_line: Optional[int] = None
    end_column: Optional[int] = None

    def __str__(self):
        return f"{self.path}:{self.line}:{self.column}: " \
               f"{self.code} {self.text}"


class ProblemEncoder(json.JSONEncoder):
    def default(self, o):
        return asdict(o)


def flake8_to_problem(raw: ProblemJson) -> Problem:
    return Problem(
        "flake8",
        raw["filename"],
        raw["line_number"],
        raw["column_number"],
        raw["code"],
        raw["text"]
    )


def pylint_to_problem(raw: ProblemJson) -> Problem:
    return Problem(
        "pylint",
        raw["path"],
        raw["line"],
        raw["column"],
        raw["message-id"],
        raw["message"],
        raw["endLine"],
        raw["endColumn"]
    )


def lint_any(filename, command, result_getter, out_to_problem):
    return_code, outs, errs = ProcessHandler.run(command, timeout=10)
    if errs:
        print(errs, file=sys.stderr, end="")
        exit(return_code)
    if not outs:
        return []
    result = result_getter(json.loads(outs))
    return list(map(out_to_problem, result))


def lint_flake8(filename: str) -> List[Problem]:
    flake8_command = [sys.executable, "-m", "flake8", "--format=json", filename]
    return lint_any(filename, flake8_command, lambda r: r[filename], flake8_to_problem)


def lint_pylint(filename: str) -> List[Problem]:
    cwd = pathlib.Path(__file__).parent.resolve()
    pylint_command = [sys.executable, "-m", "pylint",
                      f'--rcfile={cwd}/.pylintrc',
                      "--output-format=json", filename]
    return lint_any(filename, pylint_command, lambda r: r, pylint_to_problem)


def lint(filename: str) -> List[Problem]:
    result = lint_flake8(filename) + lint_pylint(filename)
    result.sort(key=lambda problem: (problem.line, problem.column))
    return result


def setup_argparse():
    parser = argparse.ArgumentParser(description="Lint provided code.")
    parser.add_argument("file", metavar="FILE", help="the file to lint")
    parser.add_argument("--json", action="store_true",
                        help="should output problems in json format")
    return parser.parse_args()


def main() -> None:
    args = setup_argparse()
    result = lint(args.file)
    if args.json:
        print(json.dumps(result, indent=1, cls=ProblemEncoder))
    else:
        for problem in result:
            print(problem)


def get_explanations() -> Dict[str, Dict[str, str]]:
    return explanations


# If you are going to execute multiple commands / multiple times, add some
# sleep to not spam the terminal and CPU.
# time.sleep(1)  # wait 1 second
