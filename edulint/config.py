from edulint.config_translates import CONFIG_TRANSLATES
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum
import re
import sys

ConfigDict = Dict["Linters", List[str]]


class Linters(Enum):
    EDULINT = 0,  # keep defined first
    PYLINT = 1,
    FLAKE8 = 2

    def __str__(self: Enum) -> str:
        return self.name.lower()

    @staticmethod
    def from_str(linter_str: str) -> "Linters":
        for linter in Linters:
            if str(linter) == linter_str.lower():
                return linter
        assert False, "no such linter: " + linter_str


@dataclass
class Arg:
    to: Linters
    val: str


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


def extract_args(filename: str) -> List[Arg]:
    edulint_re = re.compile(r"\s*#[\s#]*edulint\s*", re.IGNORECASE)
    linters_re = re.compile(r"\s*(" + "|".join(str(linter) for linter in Linters) + r")\s*", re.IGNORECASE)

    result: List[Arg] = []
    with open(filename) as f:
        for line in f:
            line = line.strip()
            match = edulint_re.match(line)
            if match:
                raw_args = line[match.end():]
                specific_match = linters_re.match(raw_args)

                if specific_match:
                    linter = Linters.from_str(specific_match.group(1))
                    args = raw_args[specific_match.end():]
                else:
                    linter = Linters.EDULINT
                    args = raw_args

                result.extend(Arg(linter, arg) for arg in args.split())
    return result


def apply_translates(args: List[Arg], config_translates: Dict[str, Dict[str, str]]) -> Config:
    result: Config = Config()
    for arg in args:
        if arg.to == Linters.EDULINT:
            translated = config_translates.get(arg.val)
            if translated is None:
                print(f"edulint: unsupported argument {arg.val}", file=sys.stderr)
            else:
                to = Linters.from_str(translated["to"])
                assert to != Linters.EDULINT
                result[to].append(translated["arg"])
        else:
            result[arg.to].append(arg.val)
    return result


def get_config(filename: str, config_translates: Dict[str, Dict[str, str]] = CONFIG_TRANSLATES) -> Config:
    return apply_translates(extract_args(filename), config_translates)
