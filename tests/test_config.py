import pytest
from edulint import Config, extract_config, Linters


def mock_contents(mocker, contents) -> None:
    mocked_file = mocker.mock_open(read_data=contents)
    mocker.patch("builtins.open", mocked_file)


@pytest.mark.parametrize("contents,config", [
    ("", Config()),
    ("print(\"Hello world\")", Config()),
    ("# edulint xxx", Config({Linters.EDULINT: ["xxx"]})),
    ("# edulint pylint xxx", Config({Linters.PYLINT: ["xxx"]})),
    ("# edulint flake8 xxx", Config({Linters.FLAKE8: ["xxx"]})),
    ("# edulint xxx yyy", Config({Linters.EDULINT: ["xxx", "yyy"]})),
    ("# edulint xxx\n# edulint xxx", Config({Linters.EDULINT: ["xxx", "xxx"]})),
    ("# edulint xxx\n# edulint yyy", Config({Linters.EDULINT: ["xxx", "yyy"]})),
    ("# edulint pylint xxx\n# edulint pylint yyy", Config({Linters.PYLINT: ["xxx", "yyy"]})),
    ("# edulint xxx\n# edulint pylint yyy", Config({Linters.EDULINT: ["xxx"], Linters.PYLINT: ["yyy"]})),
    ("# edulint flake8 xxx\n# edulint pylint yyy", Config({Linters.FLAKE8: ["xxx"], Linters.PYLINT: ["yyy"]})),
    ("\n\n# edulint xxx", Config({Linters.EDULINT: ["xxx"]})),
    ("some code\n # edulint xxx\ncode mentioning edulint a bit\n# edulint yyy",
     Config({Linters.EDULINT: ["xxx", "yyy"]})),
    ("           #        edulint      xxx        ", Config({Linters.EDULINT: ["xxx"]})),
    ("           #        edulint      xxx  yyy      ", Config({Linters.EDULINT: ["xxx", "yyy"]}))
])
def test_extract_config_extracts_correctly(mocker, contents, config):
    mock_contents(mocker, contents)
    assert extract_config("foo").config == config.config
