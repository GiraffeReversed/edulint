#!/usr/bin/python3

from typing import List, Dict, Union, Optional, Callable, Any
from edulint.process_handler import ProcessHandler
from edulint.explanations import explanations
import argparse
import json
from dataclasses import dataclass, asdict
import pathlib
import sys
from enum import Enum
import re
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

    def set_source(self, v: str) -> "Problem":
        self.source = v
        return self

    def set_path(self, v: str) -> "Problem":
        self.path = v
        return self

    def set_line(self, v: int) -> "Problem":
        self.line = v
        return self

    def set_column(self, v: int) -> "Problem":
        self.column = v
        return self

    def set_code(self, v: str) -> "Problem":
        self.code = v
        return self

    def set_text(self, v: str) -> "Problem":
        self.text = v
        return self

    def set_end_line(self, v: Optional[int]) -> "Problem":
        self.end_line = v
        return self

    def set_end_column(self, v: Optional[int]) -> "Problem":
        self.end_column = v
        return self

    def __str__(self):
        return f"{self.path}:{self.line}:{self.column}: " \
               f"{self.code} {self.text}"


class ProblemEncoder(json.JSONEncoder):
    def default(self, o):
        return asdict(o)


class Linters(Enum):
    EDULINT = 0,  # keep defined first
    PYLINT = 1,
    FLAKE8 = 2

    def __str__(self: Enum) -> str:
        return self.name.lower()

    @staticmethod
    def from_str(linter_str: str) -> "Linters":
        for linter in Linters:
            if str(linter) == linter_str.lower():
                return linter
        assert False, "no such linter: " + linter_str


class Config:
    def __init__(self, config=None):
        config = config if config is not None else {}
        self.config: Dict[Linters, List[str]] = {linter: config.get(linter, []) for linter in Linters}


def extract_config(filename: str) -> Config:
    edulint_re = re.compile(r"\s*#[\s#]*edulint\s*", re.IGNORECASE)
    linters_re = re.compile(r"\s*(" + "|".join(str(linter) for linter in Linters) + r")\s*", re.IGNORECASE)

    result = Config()
    with open(filename) as f:
        for line in f:
            match = edulint_re.match(line)
            if match:
                raw_config = line[match.end():]
                specific_match = linters_re.match(raw_config)
                if specific_match:
                    result.config[Linters.from_str(specific_match.group(1))].append(raw_config[specific_match.end():])
                else:
                    result.config[Linters.EDULINT].append(raw_config)
    return result


def flake8_to_problem(raw: ProblemJson) -> Problem:
    for val, t in (("filename", str), ("line_number", int), ("column_number", int), ("code", str), ("text", str)):
        assert isinstance(raw[val], t), f"got {type(raw[val])} for {val}"

    return Problem(
        "flake8",
        raw["filename"],
        raw["line_number"],
        raw["column_number"],
        raw["code"],
        raw["text"]
    )


def pylint_to_problem(raw: ProblemJson) -> Problem:
    for val, ts in (
        ("path", [str]),
        ("line", [int]),
        ("column", [int]),
        ("message-id", [str]),
        ("message", [str]),
        ("endLine", [int, type(None)]),
            ("endColumn", [int, type(None)])):
        assert any(isinstance(raw[val], t) for t in ts), f"got {type(raw[val])} for {val}"

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


def lint_any(
        filename: str, command: List[str], config: List[str],
        result_getter: Callable[[Any], List[ProblemJson]],
        out_to_problem: Callable[[ProblemJson], Problem]) -> List[Problem]:
    return_code, outs, errs = ProcessHandler.run(command + config, timeout=10)
    if errs:
        print(errs, file=sys.stderr, end="")
        exit(return_code)
    if not outs:
        return []
    result = result_getter(json.loads(outs))
    return list(map(out_to_problem, result))


def lint_flake8(filename: str, config: Config) -> List[Problem]:
    flake8_command = [sys.executable, "-m", "flake8", "--format=json", filename]
    return lint_any(filename, flake8_command, config.config[Linters.FLAKE8], lambda r: r[filename], flake8_to_problem)


def lint_pylint(filename: str, config: Config) -> List[Problem]:
    cwd = pathlib.Path(__file__).parent.resolve()
    pylint_command = [sys.executable, "-m", "pylint",
                      f'--rcfile={cwd}/.pylintrc',
                      "--output-format=json", filename]
    return lint_any(filename, pylint_command, config.config[Linters.PYLINT], lambda r: r, pylint_to_problem)


def lint(filename: str, config: Config) -> List[Problem]:
    result = lint_flake8(filename, config) + lint_pylint(filename, config)
    result.sort(key=lambda problem: (problem.line, problem.column))
    return result


def setup_argparse() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lint provided code.")
    parser.add_argument("file", metavar="FILE", help="the file to lint")
    parser.add_argument("--json", action="store_true",
                        help="should output problems in json format")
    return parser.parse_args()


def main() -> None:
    args = setup_argparse()
    config = extract_config(args.file)
    result = lint(args.file, config)
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
