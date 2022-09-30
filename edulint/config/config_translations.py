from edulint.linters import Linter
from edulint.options import Option
from typing import Dict, List
from dataclasses import dataclass


@dataclass(frozen=True)
class Translation:
    for_linter: Linter
    vals: List[str]


CONFIG_TRANSLATIONS: Dict[Option, Translation] = {
    Option.ENHANCEMENT: Translation(
        Linter.PYLINT,
        ["--enable=no-self-use,superfluous-parens,consider-using-min-builtin,"
         "consider-using-max-builtin,consider-using-with,unspecified-encoding,"
         "use-augmenting-assignment"
         ]
    ),
    Option.PYTHON_SPEC: Translation(
        Linter.PYLINT,
        ["--enable=unidiomatic-typecheck,misplaced-format-function,"
         "unnecessary-lambda,protected-access,multiple-imports,"
         "wrong-import-position,consider-using-from-import,wildcard-import,"
         "reimported,improve-for-loop,consider-iterating-dictionary,"
         "consider-using-dict-items,consider-using-f-string,"
         "inconsistent-return-statements,consider-swap-variables,"
         "consider-using-join,consider-using-set-comprehension,"
         "unnecessary-comprehension,use-a-generator,use-list-literal,"
         "use-dict-literal,invalid-name,consider-using-in"]
    ),
    Option.ALLOWED_ONECHAR_NAMES: Translation(
        Linter.PYLINT,
        ["--bad-names-rgxs=^[a-z]$"]
    )
}


def get_config_translations() -> Dict[Option, Translation]:
    return CONFIG_TRANSLATIONS


IB111_WEEK_TRANSLATIONS: List[Translation] = [
    Translation(Linter.PYLINT, ["--disable=consider-using-in,consider-swap-variables"]),  # 0
    Translation(Linter.PYLINT, ["--disable=consider-using-in,consider-swap-variables"]),  # 1
    Translation(Linter.PYLINT, ["--disable=consider-using-in,consider-swap-variables"]),  # 2
    Translation(Linter.PYLINT, ["--disable=consider-using-in"]),  # 3
    Translation(Linter.PYLINT, ["--disable=consider-using-in"]),  # 4
    Translation(Linter.PYLINT, ["--disable=consider-using-in"]),  # 5
    Translation(Linter.PYLINT, ["--disable=consider-using-in"]),  # 6
    Translation(Linter.PYLINT, []),  # 7
    Translation(Linter.PYLINT, []),  # 8
    Translation(Linter.PYLINT, []),  # 9
    Translation(Linter.PYLINT, []),  # 10
    Translation(Linter.PYLINT, []),  # 11
    Translation(Linter.PYLINT, []),  # 12
]


def get_ib111_translations() -> List[Translation]:
    assert len(IB111_WEEK_TRANSLATIONS) == 13
    return IB111_WEEK_TRANSLATIONS
