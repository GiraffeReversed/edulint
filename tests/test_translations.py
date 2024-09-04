import os

import pytest

from edulint.options import Option
from edulint.config.arg import Arg
from edulint.config.language_translations import Translation, parse_lang_file
from test_utils import lazy_problem, apply_and_lint, get_tests_path

def get_lang_translations_path(filename):
    return get_tests_path(os.path.join("language_translations", filename))

@pytest.mark.parametrize("filename,expected_output", [
    ("R6609-pylint-translation-by-symbol.toml", {"use-augmented-assign": Translation("Use '{} {}= {}'", extracts={})}),
])
def test_parse_lang_file(filename: str, expected_output):
    assert parse_lang_file(get_lang_translations_path(filename)) == expected_output

@pytest.mark.parametrize("checked_filename,translations_filename,expected_output", [
    ("z202817-zkouska.py", "R6609-pylint-translation-by-symbol.toml", [
        lazy_problem().set_line(10).set_text("Use 'num //= 10'"),
        lazy_problem().set_line(172)
        .set_text("do not compare types, for exact checks use `is` / `is not`, for instance checks use `isinstance()`"),
        lazy_problem().set_line(196).set_text("Unnecessary pass statement"),
    ]),
    ("z202817-zkouska.py", "R6609-pylint-translation-by-code.toml", [
        lazy_problem().set_line(10).set_text("Use 'num //= 10'"),
        lazy_problem().set_line(172)
        .set_text("do not compare types, for exact checks use `is` / `is not`, for instance checks use `isinstance()`"),
        lazy_problem().set_line(196).set_text("Unnecessary pass statement"),
    ]),
    ("z202817-zkouska.py", "E721-flake8-translation-by-code.toml", [
        lazy_problem().set_line(10).set_text("Use augmented assignment: 'num //= 10'"),
        lazy_problem().set_line(172).set_text("Use isinstance"),
        lazy_problem().set_line(196).set_text("Unnecessary pass statement"),
    ]),
    ("064fe05979.py", "E712-flake8-translation-tweaked.toml", [
        lazy_problem().set_line(41).set_text("Instead of comparison with False use 'if not cond'"),
    ]),
    ("064fe05979.py", "E712-flake8-translation-swapped.toml", [
        lazy_problem().set_line(41).set_text("Use 'if not cond' instead of comparison with False"),
    ]),
    ("064fe05979.py", "E712-flake8-translation-only-second.toml", [
        lazy_problem().set_line(41).set_text("Use 'if not cond'"),
    ]),
    ("z202817-zkouska.py", "many.toml", [
        lazy_problem().set_line(10).set_text("Use 'num //= 10'"),
        lazy_problem().set_line(172).set_text("Use isinstance"),
        lazy_problem().set_line(196).set_text("You shall not pass"),
    ]),
])
def test_translations(checked_filename, translations_filename, expected_output):
    apply_and_lint(
        get_tests_path(checked_filename),
        [
            Arg(Option.PYLINT, "--enable=R6609,W0107"),
            Arg(Option.FLAKE8, "--extend-select=E721,E712"),
            Arg(Option.LANGUAGE_FILE, get_lang_translations_path(translations_filename))
        ],
        expected_output
    )

@pytest.mark.parametrize("checked_filename,translations_filename,expected_output", [
    ("z202817-zkouska.py", "config-file-direct-translations-many.toml", [
        lazy_problem().set_line(10).set_text("Use 'num //= 10'"),
        lazy_problem().set_line(172).set_text("Use isinstance"),
        lazy_problem().set_line(196).set_text("You shall not pass"),
    ]),
    ("z202817-zkouska.py", "config-file-referenced-translations-many.toml", [
        lazy_problem().set_line(10).set_text("Use 'num //= 10'"),
        lazy_problem().set_line(172).set_text("Use isinstance"),
        lazy_problem().set_line(196).set_text("You shall not pass"),
    ]),
])
def test_translations_in_config_file(checked_filename, translations_filename, expected_output):
    apply_and_lint(
        get_tests_path(checked_filename),
        [Arg(Option.CONFIG_FILE, get_lang_translations_path(translations_filename))],
        expected_output
    )
