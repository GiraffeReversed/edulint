#!/usr/bin/python3

from typing import List, Dict, Union
from process_handler import ProcessHandler
import argparse
import json
from functools import partial
# import time


Problem = Dict[str, Union[str, int]]


def main() -> None:
    parser = argparse.ArgumentParser(description="Lint provided code.")
    parser.add_argument("file", metavar="FILE", help="the file to lint")
    args = parser.parse_args()
    result = lint(args.file)
    print(json.dumps(result, indent=1))


def add_source(source : str, defect : Problem) -> Problem:
    defect["source"] = source
    return defect


def lint_flake8(filename : str) -> List[Problem]:
    flake8_command = ["python3", "-m", "flake8", "--format=json", filename]
    return_code, outs, errs = ProcessHandler.run(flake8_command)
    flake8_result = json.loads(outs)[filename]
    return list(map(partial(add_source, "flake8"), flake8_result))


def lint_pylint(filename : str) -> List[Problem]:
    pylint_command = ["python3", "-m", "pylint", "--output-format=json", filename]
    return_code, outs, errs = ProcessHandler.run(pylint_command)
    pylint_result = json.loads(outs)
    return list(map(partial(add_source, "pylint"), pylint_result))


def lint(filename : str) -> List[Problem]:
    return lint_flake8(filename) + lint_pylint(filename)


# If you are going to execute multiple commands / multiple times, add some
# sleep to not spam the terminal and CPU.
# time.sleep(1)  # wait 1 second

if __name__ == "__main__":
    main()
