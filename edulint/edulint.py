import edulint
from edulint.options import Option
from edulint.option_parses import OptionParse, get_option_parses
from edulint.config.config import get_config_many, get_cmd_args, ImmutableConfig
from edulint.config.language_translations import LangTranslations
from edulint.linting.problem import Problem
from edulint.linting.linting import lint_many, sort, EduLintLinterFailedException
from edulint.versions.version_checker import PackageInfoManager
from edulint.explanations import update_explanations, get_explanations
from typing import List, Dict, Tuple, Any
import argparse
import os
import sys
import json
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
    main_parser = argparse.ArgumentParser(prog="edulint")

    shared_options_parser = argparse.ArgumentParser(add_help=False)
    shared_options_parser.add_argument(
        "--json", action="store_true", help="should output problems in json format"
    )
    shared_options_parser.add_argument(
        "--disable-version-check",
        action="store_true",
        default=False,
        help="EduLint checks for a newer version at most once per hour. If newer version is available in pip, "
        "it will print a message to stderr. Specifying this flag disables the check completely.",
    )
    shared_options_parser.add_argument(
        "--disable-explanations-update",
        action="store_true",
        default=False,
        help="EduLint periodically updates explanations. Specifying this flag disables the updates.",
    )

    subparsers = main_parser.add_subparsers(dest="command")
    subparsers.required = True

    check_parser = subparsers.add_parser(
        "check",
        description="Lints provided code.",
        formatter_class=argparse.RawTextHelpFormatter,
        parents=[shared_options_parser],
    )
    check_parser.add_argument(
        "-o",
        "--option",
        metavar="OPTION",
        dest="options",
        default=[],
        action="append",
        help=format_options_help(option_parses),
    )
    check_parser.add_argument(
        "files_or_dirs",
        metavar="FILE-OR-DIRECTORY",
        nargs="+",
        help="the file(s) or directory(ies) to lint",
    )

    explain_parser = subparsers.add_parser(
        "explain", description="Explains check by message ID", parents=[shared_options_parser]
    )
    explain_parser.add_argument(
        "message_ids",
        metavar="MESSAGE-ID",
        nargs="+",
        help="message id (e.g., E0001); use 'all' as a message id to get all explanations",
    )

    _version_parser = subparsers.add_parser(
        "version", description="Shows installed EduLint version", parents=[shared_options_parser]
    )

    return main_parser.parse_args()


def to_json(
    configs: List[Tuple[List[str], ImmutableConfig, LangTranslations]], problems: List[Problem]
) -> str:
    def config_to_json(obj: Any) -> str:
        if isinstance(obj, ImmutableConfig):
            return {arg.option.to_name(): arg.val for arg in obj.config}
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

    config_json = json.dumps(
        [config for _files, config, _translation in configs], default=config_to_json
    )
    problems_json = Problem.schema().dumps(problems, indent=2, many=True)
    return f'{{"configs": {config_json}, "problems": {problems_json}}}'


def check_for_updates(is_check_disabled: bool = False):
    if is_check_disabled:
        return

    Thread(target=_update_check).start()


def _update_check():
    python_executable = sys.executable or (
        "python" if os.name == "nt" else "python3"
    )  # nt is Windows
    version_ttl = 600
    if PackageInfoManager.is_update_waiting("edulint", ttl=version_ttl):
        try:
            logger.warning(
                f"Update for EduLint ({PackageInfoManager.get_latest_version('edulint', version_ttl)}) is available. "
                f"You can upgrade using `{python_executable} -m pip install --upgrade --user edulint`"
            )
        except ValueError as e:
            if not (len(e.args) > 0 and e.args[0] == "I/O operation on closed file."):
                raise e


def check_code(args, option_parses):
    cmd_args = get_cmd_args(args)

    try:
        file_configs = get_config_many(args.files_or_dirs, cmd_args, option_parses=option_parses)
    except FileNotFoundError as e:
        exception = str(e)
        if exception.lower().startswith("[errno"):
            assert "]" in exception
            exception = exception[exception.index("]") + 2 :]
        logger.opt(raw=True, colors=True).critical(
            "<red>FileNotFoundError:</red> {exception}\n", exception=exception
        )
        return 3

    try:
        results = lint_many(file_configs)
    except (TimeoutError, json.decoder.JSONDecodeError, EduLintLinterFailedException):
        return 2

    sorted_results = sort(args.files_or_dirs, results)
    checks_single_file = len(args.files_or_dirs) == 1 and not os.path.isdir(args.files_or_dirs[0])

    if args.json:
        print(to_json(file_configs, sorted_results))
    else:
        prev_problem = None
        for problem in sorted_results:
            if not checks_single_file and (
                prev_problem is None or prev_problem.path != problem.path
            ):
                print(f"****************** {os.path.basename(problem.path)}")
                prev_problem = problem

            print(problem)

    return 0 if len(sorted_results) == 0 else 1


def explain_messages(args):
    explanations = get_explanations()
    if any(id_.lower() == "all" for id_ in args.message_ids):
        message_ids = explanations.keys()
    else:
        message_ids = args.message_ids

    mid_expls = {}
    for mid in message_ids:
        expl = explanations.get(mid)
        if expl is None:
            logger.warning(f"Message {mid} does not have an explanation")
        elif args.json:
            mid_expls[mid] = expl
        else:
            if len(args.message_ids) > 1:
                if mid != args.message_ids[0]:
                    print("\n")
                print(f"## {mid}")
            if expl.get("why", "").strip():
                print("### Why is it a problem?")
                print(expl["why"].strip())
                print()
            if expl.get("examples", "").strip():
                print("### How to solve it?")
                print(expl["examples"].strip())

    if args.json:
        data = {"explanations": mid_expls}
        print(json.dumps(data, indent=2))

    return 0


@logger.catch
def main() -> int:
    setup_logger()
    option_parses = get_option_parses()
    args = setup_argparse(option_parses)

    check_for_updates(args.disable_version_check)
    update_explanations(
        args.disable_explanations_update
    )  # get_explanations also can trigger update, but we're not calling it anywhere else.

    if args.command == "check":
        return check_code(args, option_parses)
    if args.command == "explain":
        return explain_messages(args)
    if args.command == "version":
        print(f"edulint version {edulint.__version__}")
        return 0
    assert False, "unreachable, but " + args.command
