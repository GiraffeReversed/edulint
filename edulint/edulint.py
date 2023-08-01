from edulint.config.config import Config, get_config, get_cmd_args
from edulint.linting.problem import Problem
from edulint.linting.linting import lint_many, sort
from typing import List, Tuple, Optional
import argparse
import os
import sys


def setup_argparse() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lints provided code.")
    parser.add_argument("-o", "--option", dest="options", default=[], action="append", help="possible option")
    parser.add_argument(
        "files_or_dirs", metavar="FILE-OR-DIRECTORY", nargs="+", help="the file(s) or directory(ies) to lint"
    )
    parser.add_argument("--json", action="store_true",
                        help="should output problems in json format")
    return parser.parse_args()


def extract_files(files_or_dirs: List[str], result: List[str] = None) -> List[str]:
    def extract_files_rec(prefix: Optional[str], files_or_dirs: List[str], result: List[str]) -> List[str]:
        for file_or_dir in files_or_dirs:
            full_path = os.path.join(prefix, file_or_dir) if prefix is not None else file_or_dir
            if os.path.isdir(full_path):
                extract_files_rec(full_path, os.listdir(full_path), result)
            elif os.path.splitext(full_path)[1] == ".py":
                result.append(full_path)
        return result

    return extract_files_rec(None, files_or_dirs, [])


def partition(files: List[str], configs: List[Config]) -> List[Tuple[List[str], Config]]:
    dedup_configs = list(set(configs))
    indices = [dedup_configs.index(config) for config in configs]
    partitioned: List[List[str]] = [[] for _ in dedup_configs]

    for i, filename in enumerate(files):
        partitioned[indices[i]].append(filename)

    if None in dedup_configs:
        partitioned.pop(dedup_configs.index(None))

    return list(zip(partitioned, dedup_configs))


def main() -> int:
    args = setup_argparse()
    cmd_args = get_cmd_args(args)

    files = extract_files(args.files_or_dirs)
    configs = [get_config(filename, cmd_args=cmd_args) for filename in files]

    try:
        result = sort(files, lint_many(partition(files, configs)))
    except TimeoutError as e:
        print(f"edulint: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(Problem.schema().dumps(result, indent=2, many=True))  # type: ignore
    else:
        prev_problem = None
        for problem in result:
            if len(files) > 1 and (prev_problem is None or prev_problem.path != problem.path):
                print(f"****************** {os.path.basename(problem.path)}")
                prev_problem = problem

            print(problem)
    return 0
