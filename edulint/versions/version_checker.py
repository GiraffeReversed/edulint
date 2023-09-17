from typing import Optional, Tuple
import os
import json
from dataclasses import dataclass
import time
from pathlib import Path

from platformdirs import PlatformDirs
from dataclasses_json import dataclass_json

from edulint.versions import pypi_helper

def current_timestamp() -> int:
    return int(time.time())


@dataclass_json
@dataclass
class PackageInfo:
    version: Optional[str] = None
    last_update_started: int = 0


class PackageInfoManager:
    @staticmethod
    def get_local_module_version(package_name: str) -> Optional[str]:
        try:
            from importlib.metadata import version  # This is only available in Python >= 3.8
            return version(package_name)
        except:
            pass

        try:
            import pkg_resources  # Part of setuptools, which might not be installed. But I don't want to include them as dependency.
            return pkg_resources.get_distribution(package_name).version
        except:
            pass

        return None

    @staticmethod
    def _create_json_file_if_doesnt_exist(filepath: str):
        if os.path.exists(filepath):
            return
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf8") as f:
            f.write("{}")

    @classmethod
    def _package_info_path(cls):
        filepath = os.path.join(PlatformDirs(appname="edulint").user_data_dir, "versions.json")
        cls._create_json_file_if_doesnt_exist(filepath)
        return filepath 

    @classmethod
    def _save_package_info_locally(cls, package_name: str, version = None, last_update_started: Optional[int] = None) -> PackageInfo:
        with open(cls._package_info_path(), "r", encoding="utf8") as f:
            data = json.load(f)

        package_info = PackageInfo.from_dict(data.get(package_name, {}))

        if version:
            package_info.version = version
        if last_update_started:
            package_info.last_update_started = last_update_started
            
        data[package_name] = package_info.to_dict()
        with open(cls._package_info_path(), "w", encoding="utf8") as f:   # I'm aware there is possible race condition between read write. Risk accepted.
            json.dump(data, f, indent=4)
        
        return package_info

    @classmethod
    def _get_package_info_locally(cls, package_name: str) -> PackageInfo:
        with open(cls._package_info_path(), "r", encoding="utf8") as f:
            data = json.load(f)
            package_info = PackageInfo.from_dict(data.get(package_name, {}))
            return package_info

    @classmethod
    def get_latest_version(cls, package_name: str, ttl = 600) -> Optional[str]:
        package_info = cls._get_package_info_locally(package_name)
        if current_timestamp() < package_info.last_update_started + ttl:
            return package_info.version  # The might be None if the previous request didn't finish yet or if it failed.

        try:
            cls._save_package_info_locally(package_name, last_update_started=current_timestamp())
            versions = pypi_helper.get_versions(package_name)
            sorted_versions = list(sorted(versions, key = lambda x: (x.major, x.minor, x.micro)))
            latest_version_str = str(sorted_versions[-1])
            cls._save_package_info_locally(package_name, version=latest_version_str)
            return latest_version_str
        except Exception as _:
            return None

    @classmethod
    def is_update_waiting(cls, package_name: str, ttl = 600) -> bool:
        local_package_version = cls.get_local_module_version(package_name)
        if local_package_version is None: # unable to determine local package version
            return False

        latest_version = cls.get_latest_version(package_name, ttl)
        
        return local_package_version != latest_version  # This presumes local version is never higher than pypi version


if __name__ == "__main__":
    print("START")
    print(PackageInfoManager.get_latest_version("edulint"))
    print("END")
