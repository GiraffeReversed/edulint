from typing import Dict, List, Optional
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


class Config:
    def __init__(self, config: Optional[ConfigDict] = None) -> None:
        config = config if config is not None else {}
        self.config: ConfigDict = {linter: config.get(linter, []) for linter in Linters}

    def __str__(self) -> str:
        return "{" + ", ".join(f"{linter}: {options}" for linter, options in self.config.items() if options) + "}"

    def __repr__(self) -> str:
        return str(self)

    def apply(self, config_translates: Dict[str, Dict[str, str]]) -> "Config":
        for arg in self.config[Linters.EDULINT]:
            translated = config_translates.get(arg)
            if translated is None:
                print(f"edulint: unsupported argument {arg}", file=sys.stderr)
            else:
                to = Linters.from_str(translated["to"])
                assert to != Linters.EDULINT
                self.config[to].append(translated["arg"])
        self.config[Linters.EDULINT] = []
        return self


def extract_config(filename: str) -> Config:
    edulint_re = re.compile(r"\s*#[\s#]*edulint\s*", re.IGNORECASE)
    linters_re = re.compile(r"\s*(" + "|".join(str(linter) for linter in Linters) + r")\s*", re.IGNORECASE)

    result: Config = Config()
    with open(filename) as f:
        for line in f:
            line = line.strip()
            match = edulint_re.match(line)
            if match:
                raw_config = line[match.end():]
                specific_match = linters_re.match(raw_config)

                if specific_match:
                    linter = Linters.from_str(specific_match.group(1))
                    config = raw_config[specific_match.end():]
                else:
                    linter = Linters.EDULINT
                    config = raw_config

                result.config[linter].extend(config.split())
    return result
