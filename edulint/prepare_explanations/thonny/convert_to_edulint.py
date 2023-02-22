from typing import Dict
from pathlib import Path

import tomli
import tomli_w

import thonny_messages

FILENAME_TOML = "thonny_pylint.toml"  # todo: set relative path to this file, not pwd?
EDULINT_TOML = "../edulint_thonny.toml"


def extract_msgs_from_thonny(reload_from_source: bool = False) -> Dict[str, Dict[str, str]]:
    if not Path(FILENAME_TOML).is_file():
        reload_from_source = True

    if reload_from_source:
        checks = thonny_messages.checks_by_id
        for check in checks.values():
            if check.get("tho_xpln"):
                check['customized_by_thonny'] = True

        with open(FILENAME_TOML, "wb") as f:
            tomli_w.dump(checks, f, multiline_strings=True)

    with open(FILENAME_TOML, "rb") as f:
        checks = tomli.load(f)

    return checks    


def convert_to_edulint():
    with open(FILENAME_TOML, "rb") as f:
        checks = tomli.load(f)

    checks = dict(filter(lambda x: x[1].get('customized_by_thonny'), checks.items()))

    answer = {}
    for key, data in checks.items():
        answer[key] = {
            'why': data['tho_xpln'],
            'examples': '',
        }

    with open(EDULINT_TOML, "wb") as f:
        tomli_w.dump(answer, f, multiline_strings=True)


if __name__ == "__main__":
    extract_msgs_from_thonny()
    convert_to_edulint()

