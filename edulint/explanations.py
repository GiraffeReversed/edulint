from typing import Dict
import toml


def get_explanations() -> Dict[str, Dict[str, str]]:
    with open('explanations.toml', encoding="utf8") as f:
        toml_str = f.read()
    parsed_toml = toml.loads(toml_str)
    return parsed_toml

# todo: add test to load explanantions (toml parser is sensitive to small mistakes)

if __name__ == "__main__":
    get_explanations()
