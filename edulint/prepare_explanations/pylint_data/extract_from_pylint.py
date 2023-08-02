import json
from pathlib import Path
from typing import Optional, Dict, Any
import os
from time import sleep

from pylint.lint import PyLinter
import tomli
import tomli_w
import requests
from tqdm import tqdm

from thonny_process_slim import make_explanation_more_friedly

# This doesn't work, but we need to version the code somewhere, so we might as well do it now.
# pylint/doc/exts/pylint_messages is not in packaged pylint, but it's in the repo
# from pylint_messages import _register_all_checkers_and_extensions, _get_all_messages, _get_message_data_path

# _get_all_messages has to be modified:
# getattr(message, "shared", False),
# getattr(message, "default_enabled", False),


SCRIPT_PATH = os.path.dirname(os.path.abspath(__file__))
PYLINT_EXPORT_JSON = os.path.join(SCRIPT_PATH, "pylint_export.json")
PYLINT_EXPORT_TOML = os.path.join(SCRIPT_PATH, "pylint_export.toml")
EDULINT_TOML = os.path.join(SCRIPT_PATH, "../edulint_pylint.toml")


class MyEncoder(json.JSONEncoder):
    def default(self, o):
        return o.__dict__


def read_file_or_empty_string(filepath: str) -> str:
    if not Path(filepath).is_file():
        return ""

    with open(filepath, encoding="utf8") as f:
        return f.read()


def pylint_to_json(output_filename: str):
    linter = PyLinter()
    _register_all_checkers_and_extensions(linter)
    messages, _ = _get_all_messages(linter)

    for severity in messages:
        problems = messages[severity]
        for i in range(len(problems)):
            data_path = _get_message_data_path(problems[i].definition)

            problems[i] = problems[i]._asdict()
            problems[i]["checker_module_path"] = "REDACTED"
            problems[i]["good_code"] = read_file_or_empty_string(data_path / "good.py")
            problems[i]["bad_code"] = read_file_or_empty_string(data_path / "bad.py")

    with open(output_filename, "w", encoding="utf8") as f:
        json.dump(messages, f, indent=4, cls=MyEncoder)


def convert_json_to_toml(input_filename: str, output_filename: str):
    with open(input_filename, encoding="utf8") as f:
        pylint_data = json.load(f)

    answer = {}
    for severity in pylint_data:
        for checker in pylint_data[severity]:
            answer[checker["id"]] = checker

            checker["level"] = severity
            checker["description"] = checker["definition"]["description"]
            checker["msg"] = checker["definition"]["msg"]
            del checker["definition"]

            del checker["shared"]  # This prop is unreliable
            del checker["default_enabled"]  # This prop is unreliable

    with open(output_filename, "wb") as f:
        tomli_w.dump(answer, f, multiline_strings=True)


def md_code_block_with_headline(code: str, headline: Optional[str] = None) -> str:
    if "# This is a placeholder for correct code for this message." in code:
        return ""

    answer = ""
    if headline:
        answer += f"\n**{headline}**\n"

    answer += f"""
```py
{code}
```
"""
    return answer


def produce_doc_link_if_available(checker: Dict[str, Any], skip_online_check: bool = True) -> str:
    non_viable_text = (
        '"**Additional details:**\n\nYou can help us make the doc better `by contributing'
    )
    if not checker["details"] or checker["details"].startswith(non_viable_text):
        return ""

    doc_url = f'https://pylint.pycqa.org/en/latest/user_guide/messages/{checker["level"]}/{checker["name"]}.html'
    if not skip_online_check:
        resp = requests.get(doc_url)
        sleep(0.5)
        if resp.status_code != 200:
            return ""

    return f'\n<a href="{doc_url}">Additional information</a>'


def convert_pylint_toml_to_edulint_toml(input_filename: str, output_filename: str):
    with open(input_filename, "rb") as f:
        data = tomli.load(f)

    edulint_data = {}

    for checker_id, checker in tqdm(data.items()):
        examples = ""
        if checker["bad_code"]:
            examples += md_code_block_with_headline(checker["bad_code"], "Problematic code")
        if checker["good_code"]:
            examples += md_code_block_with_headline(checker["good_code"], "How to fix it")

        examples += produce_doc_link_if_available(checker)

        edulint_data[checker_id] = {
            "why": make_explanation_more_friedly(checker["description"]),
            "examples": examples.lstrip(),
        }

    with open(output_filename, "wb") as f:
        tomli_w.dump(edulint_data, f, multiline_strings=True)


def process_from_stored_data():
    convert_json_to_toml(PYLINT_EXPORT_JSON, PYLINT_EXPORT_TOML)
    convert_pylint_toml_to_edulint_toml(PYLINT_EXPORT_TOML, EDULINT_TOML)


if __name__ == "__main__":
    # pylint_to_json(PYLINT_EXPORT_JSON)
    process_from_stored_data()
