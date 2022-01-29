#!/usr/bin/python3

from typing import List, Dict, Union, Optional
from process_handler import ProcessHandler
import argparse
import json
from dataclasses import dataclass, asdict
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


def lint_flake8(filename: str) -> List[Problem]:
    flake8_command = ["python3", "-m", "flake8", "--format=json", filename]
    return_code, outs, errs = ProcessHandler.run(flake8_command)
    if not outs:
        return []
    flake8_result = json.loads(outs)[filename]
    return list(map(flake8_to_problem, flake8_result))


def lint_pylint(filename: str) -> List[Problem]:
    pylint_command = ["python3", "-m", "pylint", "--output-format=json", filename]
    return_code, outs, errs = ProcessHandler.run(pylint_command)
    if not outs:
        return []
    pylint_result = json.loads(outs)
    return list(map(pylint_to_problem, pylint_result))


def lint(filename: str) -> List[Problem]:


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


# If you are going to execute multiple commands / multiple times, add some
# sleep to not spam the terminal and CPU.
# time.sleep(1)  # wait 1 second

if __name__ == "__main__":
    main()
