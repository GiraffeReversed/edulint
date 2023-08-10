from pathlib import Path
import string
import os
from typing import Dict, Any, Optional
import sys
import hashlib
import json
import time

import tomli
import requests
from platformdirs import PlatformDirs


ALLOWED_FILENAME_LETTERS = string.ascii_letters + string.digits + "-_"
ALLOW_UNRESTRICTED_LOCAL_PATHS = True
ALLOW_HTTP_S_PATHS = True


class EduLintConfigFileException(Exception):
    pass


class ConfigFileAccessMethodNotAllowedException(EduLintConfigFileException):
    pass


class InvalidConfigFile(EduLintConfigFileException):
    pass


def load_toml_file(filename_or_url: str) -> Optional[Dict[str, Any]]:
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


def _load_local_config_file(filepath: str, message: str, is_path_safe: bool = False) -> str:
    if not is_path_safe and not ALLOW_UNRESTRICTED_LOCAL_PATHS:
        raise ConfigFileAccessMethodNotAllowedException("Arbitrary local filepaths are not enabled.")

    # Doing the test in two steps should prevent possible exception during the if test.
    if not (Path(filepath).exists() and Path(filepath).is_file()):
        raise FileNotFoundError(f"Configuration file '{filepath}' not {message}.")

    with open(filepath, encoding="utf8") as f:
        return f.read()


def _load_external_config_file(url: str) -> str:
    if not ALLOW_HTTP_S_PATHS:
        raise ConfigFileAccessMethodNotAllowedException("Loading of external configs using HTTP/HTTPS is disallowed in EduLint's configuration.")

    return CachedHTTPGet.http_get(url)  # can throw exception FileNotFoundError if remote URL didn't work and file is not cached yet


class CachedHTTPGet:
    @classmethod
    def http_get(cls, url: str, max_cache_time: int = 5 * 60, max_cache_time_when_offline: int = 500 * 24 * 60) -> str:
        """
        Source priority: file cache with max age > HTTP GET from URL > file cache with extended max age
        """

        cached_version: str = cls._read_version_from_disk(url, max_age_in_seconds=max_cache_time)
        if cached_version:
            return cached_version

        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                content = resp.text
                cls._write_version_to_disk(url, content)
                return content

            print(f"Request for external config '{url}' failed with status code {resp.status_code}. Trying to fallback to cached version if available.", file=sys.stderr)

        except requests.exceptions.RequestException:
            pass

        cached_version: str = cls._read_version_from_disk(url, max_age_in_seconds=max_cache_time_when_offline)
        if cached_version:
            return cached_version
        raise FileNotFoundError(f"Request for external config '{url}' failed -- maybe you are offline or the URL is incorrect.")

    @staticmethod
    def _get_timestamp() -> int:
        return int(time.time())

    @staticmethod
    def _get_edulint_cache_folder_location() -> Path:
        path_str = PlatformDirs(appname="edulint").user_data_dir
        path = Path(path_str)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @staticmethod
    def _convert_source_to_safe_filename(source: str) -> str:
        return hashlib.sha256(source.encode(errors="replace")).hexdigest() + ".toml"

    @classmethod
    def _get_filepath_from_source(cls, source: str) -> str:
        folder_path = cls._get_edulint_cache_folder_location()
        source_filename = cls._convert_source_to_safe_filename(source)
        # future: saving everything into same folder can become problem if there are too many filder in the folder
        return folder_path / source_filename

    @classmethod
    def _get_metadata_filepath(cls, source: str) -> str:
        base_filepath = cls._get_filepath_from_source(source)
        return base_filepath.with_suffix(base_filepath.suffix + ".metadata")

    @classmethod
    def _write_version_to_disk(cls, source: str, content: str):
        try:
            with open(cls._get_filepath_from_source(source), "w", encoding="utf8") as f:
                f.write(content)  # security: writing arbitrary content from web is not great, but at least it's written as text
            with open(cls._get_metadata_filepath(source), "w", encoding="utf8") as f:
                json.dump({
                        "timestamp": cls._get_timestamp(),
                        "source": source,
                    }, f, indent=4)
        except Exception as e:
            print(f"[!] Saving cache file for configuration failed. {e}", file=sys.stderr)

    @classmethod
    def _read_version_from_disk(cls, source: str, max_age_in_seconds: int = 5 * 60) -> Optional[str]:
        try:
            with open(cls._get_metadata_filepath(source), "r", encoding="utf8") as f:
                metadata = json.load(f)
            if metadata["timestamp"] + max_age_in_seconds <= cls._get_timestamp():  # todo: int
                return None

            with open(cls._get_filepath_from_source(source), "r", encoding="utf8") as f:
                return f.read()
        except FileNotFoundError:
            return None
        except Exception as e:
            print(f"[!] Reading or parsing cache file for configuration failed. {e}", file=sys.stderr)

        return None
