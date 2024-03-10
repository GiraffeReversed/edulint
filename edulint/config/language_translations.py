from typing import Any, Dict, ClassVar
from dataclasses import dataclass
import inspect
import pkgutil
import importlib
import re

from loguru import logger

import pylint
from pylint.checkers import BaseChecker

from edulint.config.raw_flake8_patterns import FLAKE8
from edulint.linting import checkers as edulint_checkers


def to_pattern(message: str):
    return re.sub("%[rsd]", "(.*)", re.escape(message), flags=re.IGNORECASE)


def checker_classes(module):
    for module_info in pkgutil.walk_packages(module.__path__):
        submodule = importlib.import_module(f"{module.__name__}.{module_info.name}")
        for name, obj in inspect.getmembers(submodule):
            if inspect.isclass(obj) and issubclass(obj, BaseChecker) and obj != BaseChecker:
                yield obj


def get_edulint_patterns():
    messages = {}
    for checker in checker_classes(edulint_checkers):
        messages.update({code: info[0] for code, info in checker.msgs.items()})

    return messages


def get_pylint_patterns():
    messages = {}
    for checker in checker_classes(pylint.checkers):
        messages.update({code: info[0] for code, info in checker.msgs.items()})

    return messages


def get_patterns():
    return {
        code: to_pattern(message)
        for code, message in {**get_pylint_patterns(), **get_edulint_patterns(), **FLAKE8}.items()
    }


@dataclass
class Translation:
    translation: str
    patterns: ClassVar[Dict[str, str]] = get_patterns()

    def translate(self, code: str, message: str):
        pattern = self.patterns.get(code)
        if pattern is None or "(.*)" not in pattern:
            return self.translation

        match = re.match(pattern, message, flags=re.IGNORECASE)
        if not match:
            return self.translation
        return self.translation.format(*match.groups())


LangTranslations = Dict[str, Translation]


def parse_lang_translations(raw_lang_translations: Any) -> LangTranslations:
    if not isinstance(raw_lang_translations, dict):
        logger.warning(
            "langauge translations are not a dictionary but a value {val} of type {type}",
            val=raw_lang_translations,
            type=type(raw_lang_translations),
        )
        return None

    lang_translations = {}
    for id_, translation in raw_lang_translations.items():
        if not isinstance(translation, str):
            logger.warning(
                "translation for identifier {id_} is not a string but a value of type {type}",
                id_=id_,
                type=type(translation),
            )
            continue

        lang_translations[id_] = Translation(translation)

    return lang_translations
