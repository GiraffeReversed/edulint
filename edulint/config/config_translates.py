from edulint.linters import Linters
from edulint.config.arg import Arg
from typing import Dict

ConfigTranslates = Dict[str, Arg]

CONFIG_TRANSLATES: ConfigTranslates = {
    "enhancement": Arg(
        Linters.PYLINT,
        "--enable=no-self-use,superfluous-parens,consider-using-min-builtin,"
        "consider-using-max-builtin,consider-using-with,unspecified-encoding,"
        "unused-variable,unused-argument"
    ),
    "python_spec": Arg(
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
