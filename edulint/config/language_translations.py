from typing import Any, Dict


class Translation:
    pattern: str

    def translate(message: str):
        return ""


LangTranslations = Dict[str, Translation]


def parse_lang_translations(raw_lang_translations: Any) -> LangTranslations:
    return {}
