# Copied from https://github.com/GiraffeReversed/edulint-web/blob/main/setup.py

import requests
from typing import Dict, Any, List, Optional
from collections import defaultdict
import argparse

from edulint.versions.utils import Version

def _fully_released_versions(data: Dict[str, Any]) -> List[Version]:
    releases = data["releases"]

    version_ids = [v for v in releases.keys()]
    valid_versions: List[Version] = []

    for version_id in version_ids:
        has_some_builds: bool = bool(len(releases[version_id]))
        is_yanked: bool = any([x.get('yanked') for x in releases[version_id]])
        version_parsed: Optional[Version] = Version.parse(version_id)

        if has_some_builds and not is_yanked and version_parsed:
            valid_versions.append(version_parsed)
    
    return valid_versions


def _only_last_patch_of_each_minor(versions: List[Version]) -> List[Version]:
    major_minor: Dict[str, Version] = defaultdict(list)
    for version in versions:
        major_minor[f"{version.major}.{version.minor}"].append(version)
    for key in major_minor:
        major_minor[key].sort(reverse=True)
    patches_only = [major_minor[key][0] for key in major_minor]
    sorted_patches = list(sorted(patches_only, key = lambda x: (x.major, x.minor)))
    return sorted_patches


def get_versions(package_name: str = 'edulint') -> List[Version]:
    edulint_info = requests.get(f"https://pypi.org/pypi/{package_name}/json", timeout=3).json()
    version_ids: List[Version] = _fully_released_versions(edulint_info)
    return version_ids



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('package_name')
    parser.add_argument('-g', '--github', default=False, action='store_true')
    parser.add_argument('-n', '--n-versions', type=int, default=5)
    args = parser.parse_args()
   

    package_name: str = args.package_name
    github_output: bool = args.github
    number_of_versions: int = args.n_versions

    versions = get_versions(package_name)
    versions = _only_last_patch_of_each_minor(versions)
    versions_str = [str(x) for x in versions]
    choosen_versions = versions_str[-number_of_versions:]
    
    if github_output:
        versions_as_str = str(choosen_versions).replace("'", "\"")
        # answer = f'{package_name}=\'{versions_as_str}\''
        
        # https://github.com/actions/runner/issues/1660#issuecomment-1359707506
        answer = f"""{package_name}<<EOF
{versions_as_str}
EOF"""
    else:
        answer = str(choosen_versions)
    
    print(answer)
