from pathlib import Path
import string
import os
from typing import Dict, Any
import sys

import tomli
import requests


ALLOWED_FILENAME_LETTERS = string.ascii_letters + string.digits + "-_"
ALLOW_UNRESTRICTED_LOCAL_PATHS = True
ALLOW_HTTP_S_PATHS = True


class EduLintConfigFileException(Exception):
    pass


class ConfigFileAccessMethodNotAllowedException(EduLintConfigFileException):
    pass


class InvalidConfigFile(EduLintConfigFileException):
    pass


def load_toml_file(filename_or_url: str) -> Dict[str, Any]:
    try:
        file_content = _load_file_from_uri(filename_or_url)
    except Exception as e:
        print(
            f"edulint: Error locating config file '{filename_or_url}': {e}",
            file=sys.stderr,
        )
        return None

    try:
        file_toml = tomli.loads(file_content)
        return file_toml
    except tomli.TOMLDecodeError as e:
        print(
            f"edulint: Invalid TOML config file '{filename_or_url}': {e}",
            file=sys.stderr,
        )
        return None


def _load_file_from_uri(path_or_url: str) -> str:
    if path_or_url.startswith(("http://", "https://")):
        return _load_external_config_file(path_or_url)

    if _only_acceptable_chars(path_or_url):
        return _load_packaged_config_file(path_or_url)

    return _load_local_config_file(path_or_url, "found locally")


def _only_acceptable_chars(filepath: str) -> bool:
    return all([x in ALLOWED_FILENAME_LETTERS for x in filepath])


def _load_packaged_config_file(filename: str) -> str:
    assert _only_acceptable_chars(filename)

    relative_path = os.path.join(os.path.dirname(__file__), "files", filename + ".toml")
    return _load_local_config_file(relative_path, "packaged", is_path_safe=True)


def _load_local_config_file(
    filepath: str, message: str, is_path_safe: bool = False
) -> str:
    if not is_path_safe and not ALLOW_UNRESTRICTED_LOCAL_PATHS:
        raise ConfigFileAccessMethodNotAllowedException(
            "Arbitrary local filepaths are not enabled."
        )

    # Doing the test in two steps should prevent possible exception during the if test.
    if not (Path(filepath).exists() and Path(filepath).is_file()):
        raise FileNotFoundError(f"Configuration file '{filepath}' not {message}.")

    with open(filepath, encoding="utf8") as f:
        return f.read()


def _load_external_config_file(url: str) -> str:
    if not ALLOW_HTTP_S_PATHS:
        raise ConfigFileAccessMethodNotAllowedException(
            "Loading of external configs using HTTP/HTTPS is disallowed in EduLint's configuration."
        )

    resp = requests.get(url)
    if resp.status_code != 200:
        raise FileNotFoundError(
            f"Request for external config '{url}' failed with status code {resp.status_code}."
        )

    return resp.content.decode()
