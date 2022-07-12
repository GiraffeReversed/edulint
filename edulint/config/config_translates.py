from edulint.linters import Linters
from edulint.options import Option
from typing import Dict
from dataclasses import dataclass


@dataclass(frozen=True)
class Translation:
    to: Linters
    val: str


CONFIG_TRANSLATIONS: Dict[Option, Translation] = {
    Option.ENHANCEMENT: Translation(
        Linters.PYLINT,
        "--enable=no-self-use,superfluous-parens,consider-using-min-builtin,"
        "consider-using-max-builtin,consider-using-with,unspecified-encoding,"
        "unused-variable,unused-argument"
    ),
    Option.PYTHON_SPEC: Translation(
        Linters.PYLINT,
        "--enable=unidiomatic-typecheck,misplaced-format-function,"
        "unnecessary-lambda,protected-access,multiple-imports,"
        "wrong-import-position,consider-using-from-import,wildcard-import,"
        "reimported,consider-using-enumerate,consider-iterating-dictionary,"
        "consider-using-dict-items,consider-using-f-string,"
        "inconsistent-return-statements,consider-swap-variables,"
        "consider-using-join,consider-using-set-comprehension,"
        "unnecessary-comprehension,use-a-generator,use-list-literal,"
        "use-dict-literal,invalid-name"
    )
}


def get_config_translations() -> Dict[Option, Translation]:
    return CONFIG_TRANSLATIONS
