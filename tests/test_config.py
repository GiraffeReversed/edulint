import pytest
from edulint.linters import Linter
from edulint.config.arg import UnprocessedArg, ProcessedArg
from edulint.options import Option, DEFAULT_CONFIG
from edulint.option_parses import OptionParse, get_option_parses, TakesVal, Type, Combine
from edulint.config.arg import Arg
from edulint.config.config import (
    Config,
    extract_args,
    parse_args,
    parse_config_file,
    get_config_many,
    get_config_one,
)
from edulint.config.config_translations import Translation, Translations
from edulint.linting.tweakers import get_tweakers
from utils import get_tests_path, remote_empty_config_url
from typing import List, Set, Dict, Tuple, Optional
from pathlib import Path


@pytest.fixture
def all_advertised_options() -> List[Option]:
    return list(get_option_parses().keys())


@pytest.fixture
def advertised_options(all_advertised_options: List[Option]) -> Set[Option]:
    return set(all_advertised_options)


@pytest.fixture
def always_managed_options() -> Set[Option]:
    return set(
        (
            Option.CONFIG,
            Option.PYLINT,
            Option.FLAKE8,
            Option.NO_FLAKE8,
            Option.IGNORE_INFILE_CONFIG_FOR,
            Option.EXPORT_GROUPS,
            Option.SET_GROUPS,
        )
    )


@pytest.fixture
def managed_tweaker_options() -> List[Set[Option]]:
    return list(tweaker.used_options for tweaker in get_tweakers().values())


@pytest.fixture
def managed_options(
    always_managed_options: Set[Option], managed_tweaker_options: List[Set[Option]]
) -> Set[Option]:
    return always_managed_options | set(
        opt for options in managed_tweaker_options for opt in options
    )


def issubset(subset, superset):
    diff = subset - superset
    assert not diff


def test_no_duplicate_advertised_options(all_advertised_options, advertised_options):
    issubset(set(all_advertised_options), advertised_options)


def test_all_advertised_options_managed(
    advertised_options: List[Option], managed_options: Set[Option]
):
    issubset(advertised_options, managed_options)


def test_all_managed_options_are_advertised(
    advertised_options: List[Option], managed_options: Set[Option]
) -> None:
    issubset(managed_options, advertised_options)


def mock_contents(mocker, contents) -> None:
    mocked_file = mocker.mock_open(read_data=contents)
    mocker.patch("builtins.open", mocked_file)


@pytest.mark.parametrize(
    "contents,args",
    [
        ("", []),
        ('print("Hello world")', []),
        ("# edulint: xxx", ["xxx"]),
        ("# edulint xxx", []),
        ("# edulint: pylint=xxx", ["pylint=xxx"]),
        ("# edulint: flake8=xxx", ["flake8=xxx"]),
        ("# edulint: xxx yyy", ["xxx", "yyy"]),
        ("# edulint: xxx\n# edulint: xxx", ["xxx", "xxx"]),
        ("# edulint: xxx\n# edulint: yyy", ["xxx", "yyy"]),
        ("# edulint: pylint=xxx\n# edulint: pylint=yyy", ["pylint=xxx", "pylint=yyy"]),
        ("# edulint: xxx\n# edulint: pylint=yyy", ["xxx", "pylint=yyy"]),
        ("# edulint: flake8=xxx\n# edulint: pylint=yyy", ["flake8=xxx", "pylint=yyy"]),
        ("\n\n# edulint: xxx", ["xxx"]),
        (
            "some code\n # edulint: xxx\ncode mentioning edulint a bit\n# edulint: yyy",
            ["xxx", "yyy"],
        ),
        ("           #        edulint:      xxx        ", ["xxx"]),
        ("           #        edulint:      xxx  yyy      ", ["xxx", "yyy"]),
        ('# edulint: pylint="xxx       yyy"', ["pylint=xxx       yyy"]),
        (
            '# edulint: pylint=xxx yyy zzz flake8=aaa bbb pylint= flake8="xxx yyy" ',
            ["pylint=xxx", "yyy", "zzz", "flake8=aaa", "bbb", "pylint=", "flake8=xxx yyy"],
        ),
        (
            "# edulint: pylint=--enable=missing-module-docstring",
            ["pylint=--enable=missing-module-docstring"],
        ),
        ("from ib111 import week_12", ["config=ib111.toml"]),
        ("from ib111 import week_02  # noqa", ["config=ib111.toml"]),
        ("#from ib111 import week_02", ["config=ib111.toml"]),
    ],
)
def test_extract_args(mocker, contents, args):
    mock_contents(mocker, contents)
    assert extract_args("foo") == args


@pytest.fixture
def options() -> Dict[Option, OptionParse]:
    return {
        Option.SET_GROUPS: OptionParse(
            Option.SET_GROUPS, "", TakesVal.YES, [], Type.LIST, Combine.REPLACE
        ),
        Option.FLAKE8: OptionParse(Option.FLAKE8, "", TakesVal.YES, [], Type.STR, Combine.EXTEND),
        Option.CONFIG: OptionParse(
            Option.CONFIG, "", TakesVal.YES, DEFAULT_CONFIG, Type.STR, Combine.REPLACE
        ),
    }


@pytest.mark.parametrize(
    "raw,parsed",
    [
        (["set-groups=python-specific"], [UnprocessedArg(Option.SET_GROUPS, "python-specific")]),
        (["flake8=foo"], [UnprocessedArg(Option.FLAKE8, "foo")]),
        (["flake8="], [UnprocessedArg(Option.FLAKE8, "")]),
        (
            ["set-groups=python-specific", "flake8=foo"],
            [
                UnprocessedArg(Option.SET_GROUPS, "python-specific"),
                UnprocessedArg(Option.FLAKE8, "foo"),
            ],
        ),
        (["flake8=--enable=xxx"], [UnprocessedArg(Option.FLAKE8, "--enable=xxx")]),
        (["set-groups=ib111-week-02"], [UnprocessedArg(Option.SET_GROUPS, "ib111-week-02")]),
        (
            ["set-groups=ib111-week-12", "set-groups=ib111-week-02"],
            [
                UnprocessedArg(Option.SET_GROUPS, "ib111-week-12"),
                UnprocessedArg(Option.SET_GROUPS, "ib111-week-02"),
            ],
        ),
        (["config=empty"], [UnprocessedArg(Option.CONFIG, "empty")]),
    ],
)
def test_parse_args(
    raw: List[str], options: Dict[Option, OptionParse], parsed: List[UnprocessedArg]
) -> None:
    assert parse_args(raw, options) == parsed


def packaged_config_files():
    packaged_config_dir = Path(__file__).parent / ".." / "edulint" / "config" / "files"
    return [c.stem for c in packaged_config_dir.iterdir() if c.suffix == ".toml"]


@pytest.mark.parametrize("config_name", packaged_config_files())
def test_packaged_configs_parse(config_name: str):
    assert parse_config_file(config_name, get_option_parses()) is not None


def test_remote_config_parses():
    url = remote_empty_config_url()
    assert parse_config_file(url, get_option_parses()) is not None


def test_local_config_found_relative_to_file():
    filename = get_tests_path(str(Path() / "file" / "somewhere" / "deep" / "03-d4_points.py"))
    iconfig = get_config_one(filename, [])

    assert iconfig[Option.CONFIG] == "enable-missing-docstring.toml"
    assert iconfig[Option.PYLINT][-1] == "--enable=missing-function-docstring"


def test_local_configs_found_relative_to_files():
    filename1 = get_tests_path(str(Path() / "file" / "somewhere" / "deep" / "03-d4_points.py"))
    filename2 = get_tests_path(str(Path() / "file" / "somewhere" / "else" / "03-d4_points.py"))
    iconfigs = get_config_many([filename1, filename2], [])

    assert len(iconfigs) == 2
    iconfig1 = iconfigs[0][1]
    iconfig2 = iconfigs[1][1]

    assert iconfig1[Option.CONFIG] == "enable-missing-docstring.toml"
    assert iconfig1[Option.PYLINT][-1] == "--enable=missing-function-docstring"

    assert iconfig2[Option.CONFIG] == "enable-missing-docstring.toml"
    assert iconfig2[Option.PYLINT][-1] == "--enable=missing-module-docstring"


@pytest.fixture
def translations() -> Translations:
    return {
        "enhancement": Translation({Linter.PYLINT: ["aaa"]}),
        "python-specific": Translation({Linter.PYLINT: ["bbb"]}),
        Option.ALLOWED_ONECHAR_NAMES.to_name(): Translation({Linter.PYLINT: ["ccc"]}),
        "ib111-week-00": Translation({Linter.PYLINT: ["iii"]}),
        "ib111-week-02": Translation({Linter.PYLINT: ["kkk"]}),
        "ib111-week-12": Translation({Linter.PYLINT: ["lll"]}),
    }


@pytest.mark.parametrize(
    "args,config",
    [
        (
            [UnprocessedArg(Option.SET_GROUPS, "enhancement")],
            [
                ProcessedArg(Option.SET_GROUPS, ["enhancement"]),
                ProcessedArg(Option.PYLINT, ["aaa"]),
            ],
        ),
        (
            [
                UnprocessedArg(Option.SET_GROUPS, "enhancement"),
                UnprocessedArg(Option.PYLINT, "zzz"),
            ],
            [
                ProcessedArg(Option.SET_GROUPS, ["enhancement"]),
                ProcessedArg(Option.PYLINT, ["aaa", "zzz"]),
            ],
        ),
        (
            [
                UnprocessedArg(Option.PYLINT, "zzz"),
                UnprocessedArg(Option.SET_GROUPS, "enhancement"),
            ],
            [
                ProcessedArg(Option.PYLINT, ["zzz", "aaa"]),
                ProcessedArg(Option.SET_GROUPS, ["enhancement"]),
            ],
        ),
        (
            [
                UnprocessedArg(Option.FLAKE8, "zzz"),
                UnprocessedArg(Option.SET_GROUPS, "enhancement"),
            ],
            [
                ProcessedArg(Option.FLAKE8, ["zzz"]),
                ProcessedArg(Option.SET_GROUPS, ["enhancement"]),
                ProcessedArg(Option.PYLINT, ["aaa"]),
            ],
        ),
        (
            [UnprocessedArg(Option.ALLOWED_ONECHAR_NAMES, "n")],
            [ProcessedArg(Option.ALLOWED_ONECHAR_NAMES, "n"), ProcessedArg(Option.PYLINT, ["ccc"])],
        ),
        (
            [UnprocessedArg(Option.SET_GROUPS, "ib111-week-02")],
            [
                ProcessedArg(Option.SET_GROUPS, ["ib111-week-02"]),
                ProcessedArg(Option.PYLINT, ["kkk"]),
            ],
        ),
        (
            [
                UnprocessedArg(Option.SET_GROUPS, "ib111-week-12"),
                UnprocessedArg(Option.SET_GROUPS, "ib111-week-02"),
            ],
            [
                ProcessedArg(Option.SET_GROUPS, ["ib111-week-02"]),
                ProcessedArg(Option.PYLINT, ["kkk"]),
            ],
        ),
        (
            [
                UnprocessedArg(Option.SET_GROUPS, "ib111-week-02"),
                UnprocessedArg(Option.PYLINT, "aaa"),
            ],
            [
                ProcessedArg(Option.SET_GROUPS, ["ib111-week-02"]),
                ProcessedArg(Option.PYLINT, ["kkk", "aaa"]),
            ],
        ),
        (
            [
                UnprocessedArg(Option.SET_GROUPS, "ib111-week-12"),
                UnprocessedArg(Option.SET_GROUPS, "enhancement"),
            ],
            [
                ProcessedArg(Option.SET_GROUPS, ["enhancement"]),
                ProcessedArg(Option.PYLINT, ["aaa"]),
            ],
        ),
        (
            [
                UnprocessedArg(Option.SET_GROUPS, "ib111-week-12,enhancement"),
            ],
            [
                ProcessedArg(Option.SET_GROUPS, ["ib111-week-12", "enhancement"]),
                ProcessedArg(Option.PYLINT, ["lll", "aaa"]),
            ],
        ),
        (
            [UnprocessedArg(Option.IGNORE_INFILE_CONFIG_FOR, "pylint,flake8")],
            [ProcessedArg(Option.IGNORE_INFILE_CONFIG_FOR, ["pylint", "flake8"])],
        ),
        (
            [UnprocessedArg(Option.IGNORE_INFILE_CONFIG_FOR, "")],
            [ProcessedArg(Option.IGNORE_INFILE_CONFIG_FOR, [])],
        ),
        ([UnprocessedArg(Option.SET_GROUPS, "")], [ProcessedArg(Option.SET_GROUPS, [])]),
        (
            [
                UnprocessedArg(Option.SET_GROUPS, "ib111-week-12"),
                UnprocessedArg(Option.SET_GROUPS, "enhancement"),
            ],
            [
                ProcessedArg(Option.SET_GROUPS, ["enhancement"]),
                ProcessedArg(Option.PYLINT, ["aaa"]),
            ],
        ),
    ],
)
def test_combine_and_translate_translates(
    args: List[UnprocessedArg], translations: Translations, config: List[ProcessedArg]
) -> None:
    def fill_in_defaults(
        config: List[ProcessedArg], option_parses: Dict[Option, OptionParse]
    ) -> List[ProcessedArg]:
        result = [ProcessedArg(o, Config._to_immutable(option_parses[o].default)) for o in Option]
        for arg in config:
            result[int(arg.option)] = ProcessedArg(arg.option, Config._to_immutable(arg.val))
        return tuple(result)

    option_parses = get_option_parses()
    result = Config("test", args, option_parses).to_immutable(translations)
    reference = fill_in_defaults(config, option_parses)
    assert result.config == reference


def _fill_in_file_config(config: Config) -> Config:
    file_config_translations = parse_config_file(
        config.get_last_value(Option.CONFIG, use_default=True), get_option_parses()
    )
    assert file_config_translations is not None
    file_config, translations = file_config_translations
    return Config.combine(file_config, config).to_immutable(translations)


def _arg_to_str(option: Option, val: Optional[str]) -> str:
    if val is None:
        return option.to_name()
    return f"{option.to_name()}={val}"


@pytest.mark.parametrize(
    "filename,cmd,args",
    [
        ("custom_set_empty_config.py", [], [Arg(Option.CONFIG, "empty")]),
        (
            "custom_set_empty_config.py",
            [_arg_to_str(Option.CONFIG, "default")],
            [Arg(Option.CONFIG, "default")],
        ),
        (
            "custom_set_empty_config.py",
            [_arg_to_str(Option.IGNORE_INFILE_CONFIG_FOR, Linter.EDULINT.to_name())],
            [Arg(Option.IGNORE_INFILE_CONFIG_FOR, "edulint"), Arg(Option.CONFIG, "default")],
        ),
        (
            "custom_set_empty_config.py",
            [_arg_to_str(Option.IGNORE_INFILE_CONFIG_FOR, "all")],
            [Arg(Option.IGNORE_INFILE_CONFIG_FOR, "all"), Arg(Option.CONFIG, "default")],
        ),
        ("custom_set_ignore_infile_and_some.py", [], [Arg(Option.IGNORE_INFILE_CONFIG_FOR, "all")]),
        ("custom_set_replace_option.py", [], [Arg(Option.SET_GROUPS, "ib111-week-01")]),
        (
            "custom_set_replace_option.py",
            [_arg_to_str(Option.SET_GROUPS, "ib111-week-05")],
            [
                Arg(Option.SET_GROUPS, "ib111-week-01"),
                Arg(Option.SET_GROUPS, "ib111-week-05"),
            ],
        ),
    ],
)
def test_get_config_one(filename: str, cmd: List[str], args: List[UnprocessedArg]):
    iconfig = _fill_in_file_config(Config("test", args))
    assert get_config_one(get_tests_path(filename), cmd).config == iconfig.config


@pytest.mark.parametrize(
    "filenames,partition",
    [
        (
            [
                Path("tests/data/custom_nonpep_assign.py"),
                Path("tests/data/custom_flake8_pylint_config.py"),
            ],
            [
                ([Path("tests/data/custom_nonpep_assign.py")], Config(enabler=None)),
                (
                    [Path("tests/data/custom_flake8_pylint_config.py")],
                    Config(
                        enabler=None,
                        config=[Arg(Option.PYLINT, "--enable=missing-module-docstring")],
                    ),
                ),
            ],
        )
    ],
)
def test_get_config_many(filenames: List[str], partition: List[Tuple[List[str], Config]]):
    configs = get_config_many(filenames, [])
    assert len(configs) == len(partition)

    for i in range(len(configs)):
        fns1, iconfig1 = configs[i]
        fns2, config2 = partition[i]

        assert fns1 == fns2

        iconfig2 = _fill_in_file_config(config2)
        assert iconfig1.config == iconfig2.config
