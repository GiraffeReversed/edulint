from typing import Dict
import os

import tomli

SCRIPT_PATH = os.path.dirname(os.path.abspath(__file__))
EXPLANATIONS_FILENAME = os.path.join(SCRIPT_PATH, "explanations.toml")


def get_explanations() -> Dict[str, Dict[str, str]]:
    with open(EXPLANATIONS_FILENAME, "rb") as f:
        parsed_toml = tomli.load(f)
    return parsed_toml


# todo: add test to load explanantions (toml parser is sensitive to small mistakes)

if __name__ == "__main__":
    get_explanations()
