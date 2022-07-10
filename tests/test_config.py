import pytest
from edulint.linters import Linters
from edulint.config.arg import Arg
from edulint.config.config import Config, extract_args, apply_translates
from edulint.config.config_translates import ConfigTranslations


def mock_contents(mocker, contents) -> None:
    mocked_file = mocker.mock_open(read_data=contents)
    mocker.patch("builtins.open", mocked_file)


@pytest.mark.parametrize("contents,args", [
    ("", []),
    ("print(\"Hello world\")", []),
    ("# edulint xxx", [Arg(Linters.EDULINT, "xxx")]),
    ("# edulint pylint xxx", [Arg(Linters.PYLINT, "xxx")]),
    ("# edulint flake8 xxx", [Arg(Linters.FLAKE8, "xxx")]),
    ("# edulint xxx yyy", [Arg(Linters.EDULINT, "xxx"), Arg(Linters.EDULINT, "yyy")]),
    ("# edulint xxx\n# edulint xxx", [Arg(Linters.EDULINT, "xxx"), Arg(Linters.EDULINT, "xxx")]),
    ("# edulint xxx\n# edulint yyy", [Arg(Linters.EDULINT, "xxx"), Arg(Linters.EDULINT, "yyy")]),
    ("# edulint pylint xxx\n# edulint pylint yyy", [Arg(Linters.PYLINT, "xxx"), Arg(Linters.PYLINT, "yyy")]),
    ("# edulint xxx\n# edulint pylint yyy", [Arg(Linters.EDULINT, "xxx"), Arg(Linters.PYLINT, "yyy")]),
    ("# edulint flake8 xxx\n# edulint pylint yyy", [Arg(Linters.FLAKE8, "xxx"), Arg(Linters.PYLINT, "yyy")]),
    ("\n\n# edulint xxx", [Arg(Linters.EDULINT, "xxx")]),
    ("some code\n # edulint xxx\ncode mentioning edulint a bit\n# edulint yyy",
     [Arg(Linters.EDULINT, "xxx"), Arg(Linters.EDULINT, "yyy")]),
    ("           #        edulint      xxx        ", [Arg(Linters.EDULINT, "xxx")]),
    ("           #        edulint      xxx  yyy      ", [Arg(Linters.EDULINT, "xxx"), Arg(Linters.EDULINT, "yyy")])
])
def test_extract_args_extracts_correctly(mocker, contents, args):
    mock_contents(mocker, contents)
    assert extract_args("foo") == args


@pytest.fixture
def config_translates() -> ConfigTranslations:
    return {"xxx": Arg(Linters.PYLINT, "yyy")}


@pytest.mark.parametrize("args,config", [
    ([Arg(Linters.EDULINT, "xxx")], Config({Linters.PYLINT: ["yyy"]})),
    ([Arg(Linters.EDULINT, "xxx"), Arg(Linters.PYLINT, "zzz")], Config({Linters.PYLINT: ["yyy", "zzz"]})),
    ([Arg(Linters.PYLINT, "zzz"), Arg(Linters.EDULINT, "xxx")], Config({Linters.PYLINT: ["zzz", "yyy"]})),
])
def test_apply_translations_translates_correctly(args, config_translates, config):
    return apply_translates(args, config_translates).config == config.config
