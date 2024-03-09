from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from loguru import logger

from edulint.linters import Linter
from edulint.config.utils import config_file_val_to_str
from edulint.option_parses import OPTION_SETS_LABEL


@dataclass
class OptionSet:
    to: Dict[Linter, List[str]] = field(default_factory=dict)
    description: str = ""


OptionSets = Dict[str, OptionSet]


def parse_option_sets(raw_option_sets: Any) -> Optional[OptionSets]:
    if not isinstance(raw_option_sets, dict):
        logger.warning(
            "option sets are not a dictionary but a value {val} of type {type}",
            val=raw_option_sets,
            type=type(raw_option_sets),
        )
        return None

    option_sets = {}
    for name, to in raw_option_sets.items():
        if not isinstance(to, dict):
            logger.warning(
                "option set named {name} is not a dictionary but a value {val} of type {type}",
                name=name,
                val=to,
                type=type(to),
            )
            continue

        option_set = OptionSet()
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
                str_val = config_file_val_to_str(OPTION_SETS_LABEL, processed)
                if str_val:
                    result.append(str_val)

            if len(result) > 0:
                option_set.to[linter] = result

        if len(option_set.to) > 0:
            option_sets[name] = option_set

    return option_sets
