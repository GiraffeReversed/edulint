from typing import Dict
import tomli


def get_explanations() -> Dict[str, Dict[str, str]]:
    with open('explanations.toml', "rb") as f:
        parsed_toml = tomli.load(f)
    return parsed_toml

# todo: add test to load explanantions (toml parser is sensitive to small mistakes)

if __name__ == "__main__":
    get_explanations()
