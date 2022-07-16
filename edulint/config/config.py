from edulint.config.arg import Arg
from edulint.options import Option, OptionParse, get_option_parses, get_name_to_option
from edulint.linters import Linters
from edulint.config.config_translates import get_config_translations, Translation
from typing import Dict, List, Optional, Tuple, Any
import re
import sys
import shlex

ConfigDict = Dict[Linters, List[str]]


class Config:
    def __init__(self, edulint: Optional[List[Arg]] = None, others: Optional[ConfigDict] = None) -> None:
        self.edulint = edulint if edulint is not None else []
        others = others if others is not None else {}
        self.others: ConfigDict = {linter: others.get(linter, []) for linter in Linters}

    @staticmethod
    def get_val_from(args: List[Arg], option: Option) -> Optional[str]:
        for arg in args:
            if arg.option == option:
                return arg.val
        return None

    @staticmethod
    def has_opt_in(args: List[Arg], option: Option) -> bool:
        return Config.get_val_from(args, option) is not None

    def get_val(self, option: Option) -> Optional[str]:
        return Config.get_val_from(self.edulint, option)

    def has_opt(self, option: Option) -> bool:
        return Config.has_opt_in(self.edulint, option)

    def __str__(self) -> str:
        def to_str(linter: Linters, options: Any) -> str:
            return f"{linter}: {options}"
        return "{" \
            + ", ".join(to_str(linter, options) for linter, options in self.others.items() if options) \
            + ", " + to_str(Linters.EDULINT, self.edulint) \
            + "}"

    def __repr__(self) -> str:
        return str(self)


def extract_args(filename: str) -> List[str]:
    edulint_re = re.compile(r"\s*#[\s#]*edulint\s*", re.IGNORECASE)

    result: List[str] = []
    with open(filename) as f:
        for i, line in enumerate(f):
            line = line.strip()
            edmatch = edulint_re.match(line)
            if not edmatch:
                continue

            raw_args = line[edmatch.end():]
            result.extend(shlex.split(raw_args))
    return result


def parse_args(args: List[str], option_parses: Dict[Option, OptionParse]) -> List[Arg]:
    name_to_option = get_name_to_option(option_parses)

    def get_name_val(arg: str) -> Tuple[str, Optional[str]]:
        if "=" in arg:
            assert arg.count("=") == 1
            name, val = arg.split("=")
            return name, val
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
    result: Config = Config(edulint=args)
    for arg in args:
        translated = config_translations.get(arg.option)
        if translated is not None:
            assert translated.to != Linters.EDULINT
            result.others[translated.to].extend(translated.val)
        elif arg.option == Option.PYLINT:
            assert arg.val
            result.others[Linters.PYLINT].append(arg.val)
        elif arg.option == Option.FLAKE8:
            assert arg.val
            result.others[Linters.FLAKE8].append(arg.val)
    return result


def get_config(
        filename: str, option_parses: Dict[Option, OptionParse] = get_option_parses(),
        config_translations: Dict[Option, Translation] = get_config_translations()) -> Config:
    return apply_translates(parse_args(extract_args(filename), option_parses), config_translations)
