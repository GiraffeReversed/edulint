from edulint.options import Option
from edulint.option_parses import OptionParse, get_option_parses
from edulint.config.config import get_config_many, get_cmd_args, ImmutableConfig
from edulint.linting.problem import Problem
from edulint.linting.linting import lint_many, sort, EduLintLinterFailedException
from edulint.versions.version_checker import PackageInfoManager
from typing import List, Optional, Dict, Tuple, Any
import argparse
import os
import sys
import json
import sys
from threading import Thread
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


def format_options_help(option_parses: Dict[Option, OptionParse]) -> str:
    def extract_line(words: List[str], max_len: int, start_i: int) -> Tuple[str, int]:
        result = [words[start_i]]
        current_len = len(words[start_i])
        for i in range(start_i + 1, len(words)):
            next_len = current_len + 1 + len(words[i])
            if next_len > max_len:
                return " ".join(result), i
            result.append(words[i])
            current_len += 1 + len(words[i])
        return " ".join(result), len(words)

    result = []
    for op in option_parses.values():
        words = (op.help_).split(" ")
        i = 0
        while i < len(words):
            if i == 0:
                start = op.option.to_name() + "  "
            else:
                start = " " * 4
            line, i = extract_line(words, 80 - 25 - len(start), i)
            result.append(start + line)
    return "\n".join(result) + "\n"


def setup_argparse(option_parses: Dict[Option, OptionParse]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="edulint",
        description="Lints provided code.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-o",
        "--option",
        metavar="OPTION",
        dest="options",
        default=[],
        action="append",
        help=format_options_help(option_parses),
    )
    parser.add_argument(
        "files_or_dirs",
        metavar="FILE-OR-DIRECTORY",
        nargs="+",
        help="the file(s) or directory(ies) to lint",
    )
    parser.add_argument("--json", action="store_true", help="should output problems in json format")
    parser.add_argument(
        "--disable-version-check",
        action='store_true',
        default=False,
        help="EduLint checks for a newer version at most once per hour. If newer version is available in pip it will print a message to stderr. Specifying this flag disables the check completely.",
    )
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


def to_json(configs: List[ImmutableConfig], problems: List[Problem]) -> str:
    def config_to_json(obj: Any) -> str:
        if isinstance(obj, ImmutableConfig):
            return {arg.option.to_name(): arg.val for arg in obj.config}
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    config_json = json.dumps(configs, default=config_to_json)
    problems_json = Problem.schema().dumps(problems, indent=2, many=True)
    return f'{{"configs": {config_json}, "problems": {problems_json}}}'


def check_for_updates(is_check_disabled: bool = False):
    if is_check_disabled:
        return

    Thread(target=_update_check).start()


def _update_check():
    python_executable = sys.executable or ("python" if os.name == 'nt' else "python3")  # nt is Windows
    version_ttl = 600
    if PackageInfoManager.is_update_waiting("edulint", ttl=version_ttl):
        logger.warning(f"Update for EduLint ({PackageInfoManager.get_latest_version('edulint', version_ttl)}) is available. You can upgrade using `{python_executable} -m pip install --upgrade --user edulint`")


@logger.catch
def main() -> int:
    setup_logger()
    option_parses = get_option_parses()
    args = setup_argparse(option_parses)
    check_for_updates(args.disable_version_check)
    cmd_args = get_cmd_args(args)

    files = extract_files(args.files_or_dirs)
    file_configs = get_config_many(files, cmd_args, option_parses=option_parses)

    try:
        results = lint_many(file_configs)
    except (TimeoutError, json.decoder.JSONDecodeError, EduLintLinterFailedException):
        return 2

    sorted_results = sort(files, results)

    if args.json:
        print(to_json(file_configs, sorted_results))
    else:
        prev_problem = None
        for problem in sorted_results:
            if len(files) > 1 and (prev_problem is None or prev_problem.path != problem.path):
                print(f"****************** {os.path.basename(problem.path)}")
                prev_problem = problem

            print(problem)

    return 0 if len(sorted_results) == 0 else 1
