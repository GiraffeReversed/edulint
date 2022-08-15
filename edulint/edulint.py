from edulint.config.config import get_config
from edulint.linting.problem import Problem
from edulint.linting.linting import lint
import argparse


def setup_argparse() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lint provided code.")
    parser.add_argument("file", metavar="FILE", help="the file to lint")
    parser.add_argument("--json", action="store_true",
                        help="should output problems in json format")
    return parser.parse_args()


def main() -> int:
    args = setup_argparse()
    config = get_config(args.file)
    result = lint(args.file, config)
    if args.json:
        print(Problem.schema().dumps(result, indent=2, many=True))  # type: ignore
    else:
        for problem in result:
            print(problem)
    return 0
