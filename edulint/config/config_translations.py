from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from loguru import logger

from edulint.linters import Linter
from edulint.config.utils import config_file_val_to_str


@dataclass
class Translation:
    to: Dict[Linter, List[str]] = field(default_factory=dict)
    description: str = ""


Translations = Dict[str, Translation]


def parse_translations(raw_translations: Any) -> Optional[Translations]:
    if not isinstance(raw_translations, dict):
        logger.warning(
            "translations are not a dictionary but a value {val} of type {type}",
            val=raw_translations,
            type=type(raw_translations),
        )
        return None

    translations = {}
    for name, to in raw_translations.items():
        if not isinstance(to, dict):
            logger.warning(
                "translation named {name} is not a dictionary but a value {val} of type {type}",
                name=name,
                val=to,
                type=type(to),
            )
            continue

        translation = Translation()
        for linter_str, translated in to.items():
            linter = Linter.safe_from_name(linter_str)
            if linter is None:
                logger.warning(
                    "invalid value {linter} where one of {linters} is expected",
                    linter=linter_str,
                    linters=", ".join(linter.to_name() for linter in Linter),
                )
                continue

            to_process = (
                [translated] if not isinstance(translated, dict) else list(translated.items())
            )
            result = []
            for processed in to_process:
                str_val = config_file_val_to_str("translations", processed)
                if str_val:
                    result.append(str_val)

            if len(result) > 0:
                translation.to[linter] = result

        if len(translation.to) > 0:
            translations[name] = translation

    return translations
