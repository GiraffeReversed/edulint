#!/usr/bin/python3

from edulint.problem import ProblemEncoder
from edulint.config import extract_config
from edulint.config_translates import CONFIG_TRANSLATES
from edulint.linting import lint
import argparse
import json


def setup_argparse() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lint provided code.")
    parser.add_argument("file", metavar="FILE", help="the file to lint")
    parser.add_argument("--json", action="store_true",
                        help="should output problems in json format")
    return parser.parse_args()


def main() -> int:
    args = setup_argparse()
    config = extract_config(args.file)
    config.apply(CONFIG_TRANSLATES)
    result = lint(args.file, config)
    if args.json:
        print(json.dumps(result, indent=1, cls=ProblemEncoder))
    else:
        for problem in result:
            print(problem)
    return 0
