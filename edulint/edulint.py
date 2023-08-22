from edulint.config.config import get_config_many, get_cmd_args
from edulint.linting.problem import Problem
from edulint.linting.linting import lint_many, sort
from typing import List, Optional
import argparse
import os
import sys
import json
from loguru import logger


def setup_logger() -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level="WARNING",
        format="<level>{name}</level>: {message}",
        diagnose=False,
        backtrace=False,
        catch=False,
    )


def setup_argparse() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lints provided code.")
    parser.add_argument(
        "-o", "--option", dest="options", default=[], action="append", help="possible option"
    )
    parser.add_argument(
        "files_or_dirs",
        metavar="FILE-OR-DIRECTORY",
        nargs="+",
        help="the file(s) or directory(ies) to lint",
    )
    parser.add_argument("--json", action="store_true", help="should output problems in json format")
    return parser.parse_args()


def extract_files(files_or_dirs: List[str]) -> List[str]:
    def extract_files_rec(
        prefix: Optional[str], files_or_dirs: List[str], result: List[str]
    ) -> List[str]:
        for file_or_dir in files_or_dirs:
            full_path = os.path.join(prefix, file_or_dir) if prefix is not None else file_or_dir
            if os.path.isdir(full_path):
                extract_files_rec(full_path, os.listdir(full_path), result)
            elif os.path.splitext(full_path)[1] == ".py":
                result.append(full_path)
        return result

    return extract_files_rec(None, files_or_dirs, [])


@logger.catch
def main() -> int:
    setup_logger()
    args = setup_argparse()
    cmd_args = get_cmd_args(args)

    files = extract_files(args.files_or_dirs)
    file_configs = get_config_many(files, cmd_args)

    try:
        results = lint_many(file_configs)
    except (TimeoutError, json.decoder.JSONDecodeError):
        return 2

    sorted_results = sort(files, results)

    if args.json:
        print(Problem.schema().dumps(sorted_results, indent=2, many=True))  # type: ignore
    else:
        prev_problem = None
        for problem in sorted_results:
            if len(files) > 1 and (prev_problem is None or prev_problem.path != problem.path):
                print(f"****************** {os.path.basename(problem.path)}")
                prev_problem = problem

            print(problem)

    return 0 if len(sorted_results) == 0 else 1
