from edulint.config.config import Config, get_config, get_cmd_args
from edulint.linting.problem import Problem
from edulint.linting.linting import lint_many, sort
from typing import List, Tuple
import argparse
import os


def setup_argparse() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lints provided code.")
    parser.add_argument("-o", "--option", dest="options", default=[], action="append", help="possible option")
    parser.add_argument("files", metavar="FILE", nargs="+", help="the file(s) to lint")
    parser.add_argument("--json", action="store_true",
                        help="should output problems in json format")
    return parser.parse_args()


def partition(files: List[str], configs: List[Config]) -> List[Tuple[List[str], Config]]:
    dedup_configs = list(set(configs))
    indices = [dedup_configs.index(config) for config in configs]
    partitioned: List[List[str]] = [[] for _ in dedup_configs]

    for i, filename in enumerate(files):
        partitioned[indices[i]].append(filename)

    return list(zip(partitioned, dedup_configs))


def main() -> int:
    args = setup_argparse()
    cmd_args = get_cmd_args(args)

    configs = [get_config(filename, cmd_args=cmd_args) for filename in args.files]

    result = sort(args.files, lint_many(partition(args.files, configs)))
    if args.json:
        print(Problem.schema().dumps(result, indent=2, many=True))  # type: ignore
    else:
        prev_problem = None
        for problem in result:
            if len(args.files) > 1 and (prev_problem is None or prev_problem.path != problem.path):
                print(f"****************** {os.path.basename(problem.path)}")
                prev_problem = problem

            print(problem)
    return 0
