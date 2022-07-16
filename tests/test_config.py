import pytest
from edulint.linters import Linters
from edulint.config.arg import Arg
from edulint.options import Option, OptionParse, get_option_parses
from edulint.config.config import Config, extract_args, parse_args, apply_translates
from edulint.config.config_translates import get_config_translations, Translation
from edulint.linting.tweakers import get_tweakers
from typing import List, Set, Dict
from copy import deepcopy


@pytest.fixture
def all_advertised_options() -> List[Option]:
    return list(get_option_parses().keys())


@pytest.fixture
def advertised_options(all_advertised_options: List[Option]) -> Set[Option]:
    return set(all_advertised_options)


@pytest.fixture
def always_managed_options() -> Set[Option]:
    return set((Option.PYLINT, Option.FLAKE8))


@pytest.fixture
def managed_translations_options() -> List[Option]:
    return list(get_config_translations().keys())


@pytest.fixture
def managed_tweaker_options() -> List[Set[Option]]:
    return list(tweaker.used_options for tweaker in get_tweakers().values())


@pytest.fixture
def managed_options(
        always_managed_options: Set[Option],
        managed_translations_options: List[Option],
        managed_tweaker_options: List[Set[Option]]
) -> Set[Option]:
    return always_managed_options \
        | set(managed_translations_options) \
        | set(opt for options in managed_tweaker_options for opt in options)


def issubset(subset, superset):
    diff = subset - superset
    assert not diff


def test_no_duplicate_advertised_options(all_advertised_options, advertised_options):
    issubset(set(all_advertised_options), advertised_options)


def test_all_advertised_options_managed(advertised_options: List[Option], managed_options: Set[Option]):
    issubset(advertised_options, managed_options)


def test_all_managed_options_are_advertised(advertised_options: List[Option], managed_options: Set[Option]) -> None:
    issubset(managed_options, advertised_options)


def mock_contents(mocker, contents) -> None:
    mocked_file = mocker.mock_open(read_data=contents)
    mocker.patch("builtins.open", mocked_file)


@pytest.mark.parametrize("contents,args", [
    ("", []),
    ("print(\"Hello world\")", []),
    ("# edulint xxx", ["xxx"]),
    ("# edulint pylint=xxx", ["pylint=xxx"]),
    ("# edulint flake8=xxx", ["flake8=xxx"]),
    ("# edulint xxx yyy", ["xxx", "yyy"]),
    ("# edulint xxx\n# edulint xxx", ["xxx", "xxx"]),
    ("# edulint xxx\n# edulint yyy", ["xxx", "yyy"]),
    ("# edulint pylint=xxx\n# edulint pylint=yyy", ["pylint=xxx", "pylint=yyy"]),
    ("# edulint xxx\n# edulint pylint=yyy", ["xxx", "pylint=yyy"]),
    ("# edulint flake8=xxx\n# edulint pylint=yyy", ["flake8=xxx", "pylint=yyy"]),
    ("\n\n# edulint xxx", ["xxx"]),
    ("some code\n # edulint xxx\ncode mentioning edulint a bit\n# edulint yyy",
     ["xxx", "yyy"]),
    ("           #        edulint      xxx        ", ["xxx"]),
    ("           #        edulint      xxx  yyy      ", ["xxx", "yyy"]),
    ("# edulint pylint=\"xxx       yyy\"", ["pylint=xxx       yyy"]),
    (
        "# edulint pylint=xxx yyy zzz flake8=aaa bbb pylint= flake8=\"xxx yyy\" ",
        ["pylint=xxx", "yyy", "zzz", "flake8=aaa", "bbb", "pylint=", "flake8=xxx yyy"]
    )
])
def test_extract_args_extracts_correctly(mocker, contents, args):
    mock_contents(mocker, contents)
    assert extract_args("foo") == args


@pytest.fixture
def options() -> Dict[Option, OptionParse]:
    return {
        Option.ENHANCEMENT: OptionParse(Option.ENHANCEMENT, "enhancement", "", False),
        Option.FLAKE8: OptionParse(Option.FLAKE8, "flake8", "", True)
    }


@pytest.mark.parametrize("raw,parsed", [
    (["enhancement"], [Arg(Option.ENHANCEMENT)]),
    (["flake8=foo"], [Arg(Option.FLAKE8, "foo")]),
    (["flake8="], [Arg(Option.FLAKE8, "")]),
    (["enhancement", "flake8=foo"], [Arg(Option.ENHANCEMENT), Arg(Option.FLAKE8, "foo")])
])
def test_parse_args(raw: List[str], options: Dict[Option, OptionParse], parsed: List[Arg]) -> None:
    assert parse_args(raw, options) == parsed


@pytest.fixture
def config_translations() -> Dict[Option, Translation]:
    return {
        Option.ENHANCEMENT: Translation(
            Linters.PYLINT,
            ["aaa"]
        ),
        Option.PYTHON_SPEC: Translation(
            Linters.PYLINT,
            ["bbb"]
        ),
        Option.ALLOWED_ONECHAR_NAMES: Translation(
            Linters.PYLINT,
            ["ccc"]
        )
    }


@pytest.mark.parametrize("args,config", [
    ([Arg(Option.ENHANCEMENT)], Config(others={Linters.PYLINT: ["aaa"]})),
    ([Arg(Option.ENHANCEMENT), Arg(Option.PYLINT, "zzz")], Config(others={Linters.PYLINT: ["aaa", "zzz"]})),
    ([Arg(Option.PYLINT, "zzz"), Arg(Option.ENHANCEMENT)], Config(others={Linters.PYLINT: ["zzz", "aaa"]})),
    (
        [Arg(Option.FLAKE8, "zzz"), Arg(Option.ENHANCEMENT)],
        Config(others={Linters.FLAKE8: ["zzz"], Linters.PYLINT: ["aaa"]})
    ),
    ([Arg(Option.ALLOWED_ONECHAR_NAMES, "n")], Config(others={Linters.PYLINT: ["ccc"]}))
])
def test_apply_translations_translates_correctly(
        args: List[Arg],
        config_translations: Dict[Option, Translation],
        config: Config) -> None:

    result = apply_translates(args, config_translations)
    orig_args = deepcopy(args)
    assert result.others == config.others
    assert result.edulint == orig_args
