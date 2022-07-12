from edulint.config.arg import Arg
from edulint.options import Option, OptionParse, get_option_parses, get_name_to_option
from edulint.linters import Linters
from edulint.config.config_translates import get_config_translations, Translation
from typing import Dict, List, Optional, Tuple
import re
import sys

ConfigDict = Dict[Linters, List[str]]


class Config:
    def __init__(self, config: Optional[ConfigDict] = None) -> None:
        config = config if config is not None else {}
        self.config: ConfigDict = {linter: config.get(linter, []) for linter in Linters}

    def __getitem__(self, key: Linters) -> List[str]:
        return self.config[key]

    def __str__(self) -> str:
        return "{" + ", ".join(f"{linter}: {options}" for linter, options in self.config.items() if options) + "}"

    def __repr__(self) -> str:
        return str(self)


def extract_args(filename: str) -> List[str]:
    edulint_re = re.compile(r"\s*#[\s#]*edulint\s*", re.IGNORECASE)
    arg_re = re.compile(r"([a-z0-9-]+)=(\"[^\"]*\"|[^\s\"]*)|[a-z0-9-]+", re.IGNORECASE)

    result: List[str] = []
    with open(filename) as f:
        for i, line in enumerate(f):
            line = line.strip()
            edmatch = edulint_re.match(line)
            if not edmatch:
                continue

            raw_args = line[edmatch.end():]
            for match in arg_re.finditer(raw_args):
                result.append(match[0])
    return result


def parse_args(args: List[str], option_parses: Dict[Option, OptionParse]) -> List[Arg]:
    name_to_option = get_name_to_option(option_parses)

    def get_name_val(arg: str) -> Tuple[str, Optional[str]]:
        if "=" in arg:
            assert arg.count("=") == 1
            name, val = arg.split("=")
            return name, val.strip("\"")
        return arg, None

    result: List[Arg] = []
    for arg in args:
        name, val = get_name_val(arg)
        option = name_to_option.get(name)

        if option is None:
            print(f"edulint: unrecognized option {name}", file=sys.stderr)
        else:
            option_parse = option_parses[option]
            if option_parse.takes_val and val is None:
                print(f"edulint: option {name} takes an argument but none was supplied", file=sys.stderr)
            elif not option_parse.takes_val and val is not None:
                print(f"edulint: option {name} takes no argument but {val} was supplied", file=sys.stderr)
            else:
                result.append(Arg(option, val))

    return result


def apply_translates(args: List[Arg], config_translations: Dict[Option, Translation]) -> Config:
    result: Config = Config()
    for arg in args:
        translated = config_translations.get(arg.option)
        if translated is not None:
            assert translated.to != Linters.EDULINT
            result[translated.to].append(translated.val)
        elif arg.option == Option.PYLINT:
            assert arg.val
            result[Linters.PYLINT].append(arg.val)
        elif arg.option == Option.FLAKE8:
            assert arg.val
            result[Linters.FLAKE8].append(arg.val)
    return result


def get_config(
        filename: str, option_parses: Dict[Option, OptionParse] = get_option_parses(),
        config_translations: Dict[Option, Translation] = get_config_translations()) -> Config:
    return apply_translates(parse_args(extract_args(filename), option_parses), config_translations)
