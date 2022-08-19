from edulint.linters import Linter
from edulint.options import Option
from typing import Dict, List
from dataclasses import dataclass


@dataclass(frozen=True)
class Translation:
    to: Linter
    vals: List[str]


CONFIG_TRANSLATIONS: Dict[Option, Translation] = {
    Option.ENHANCEMENT: Translation(
        Linter.PYLINT,
        ["--enable=no-self-use,superfluous-parens,consider-using-min-builtin,"
         "consider-using-max-builtin,consider-using-with,unspecified-encoding,"
         "unused-variable,unused-argument"]
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
