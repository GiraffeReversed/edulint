import os
from typing import Dict, Any
from collections import defaultdict

import tomli
import tomli_w

from pylint_data import extract_from_pylint
from thonny_data import extract_from_edulint


SCRIPT_PATH = os.path.dirname(os.path.abspath(__file__))
PYLINT_FILE = extract_from_pylint.EDULINT_TOML
THONNY_FILE = extract_from_edulint.EDULINT_TOML
MANUAL_FILE = os.path.join(SCRIPT_PATH, "edulint_manual.toml")
OUTPUT_FILE = os.path.join(SCRIPT_PATH, "../explanations.toml")


def load_toml_file(filename: str) -> Dict[str, Any]:
    with open(filename, "rb") as f:
        return tomli.load(f)


def combine_sources():
    pylint_data = load_toml_file(PYLINT_FILE)
    thonny_data = load_toml_file(THONNY_FILE)
    manual_data = load_toml_file(MANUAL_FILE)

    answer: Dict[str, Dict[str, str]] = defaultdict(dict)

    for data_source in [pylint_data, thonny_data, manual_data]:
        for check_id, check_data in data_source.items():
            for check_field_name, check_field_value in check_data.items():
                if not check_field_value:
                    continue
                answer[check_id][check_field_name] = check_field_value

    with open(OUTPUT_FILE, "wb") as f:
        tomli_w.dump(answer, f, multiline_strings=True)


def main():
    extract_from_pylint.process_from_stored_data()
    extract_from_edulint.process_from_stored_data()
    combine_sources()


if __name__ == "__main__":
    main()
