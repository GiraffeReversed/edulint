from typing import List, Set, Dict
import re
from loguru import logger

from edulint.linters import Linter
from edulint.options import Option
from edulint.linting.problem import Problem


CONFIG_PATTERNS = {
    Linter.FLAKE8: [
        re.compile(r"(.*)#\s*(noqa)", re.IGNORECASE),
        re.compile(r"(.*)#\s*(flake8: *noqa)", re.IGNORECASE),
    ],
    Linter.PYLINT: [
        re.compile(r"(.*)#\s*(pylint:\s*disable)", re.IGNORECASE),
        re.compile(r"(.*)#\s*(pylint:\s*enable)", re.IGNORECASE),
    ],
    Linter.EDULINT: [],  # handled in config
}


def report_infile_config(
    filenames: List[str], ignore_infile: Set[str], enablers: Dict[str, str]
) -> List[Problem]:
    if "all" in ignore_infile:
        ignore_infile = (ignore_infile - {"all"}) | {linter.to_name() for linter in Linter}

    patterns = []
    for ignore_infile_linter in ignore_infile:
        linter = Linter.safe_from_name(ignore_infile_linter)
        if linter is None:
            logger.warning(
                "invalid value '{val}' for option {option}",
                val=ignore_infile_linter,
                option=Option.IGNORE_INFILE_CONFIG_FOR.to_name(),
            )
            continue
        patterns.extend(CONFIG_PATTERNS[linter])

    results = []
    ib111_re = re.compile(r".*from\s+ib111\s+import", re.IGNORECASE)
    for filename in filenames:
        with open(filename, encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                for pattern in patterns:
                    match = pattern.match(line)
                    if match and ("noqa" not in match.group(2).lower() or not ib111_re.match(line)):
                        results.append(
                            Problem(
                                source=Linter.EDULINT,
                                enabled_by=enablers.get("EDL001"),
                                path=filename,
                                line=i,
                                column=len(match.group(1)),
                                code="EDL001",
                                text=f"Forbidden magic comment '{match.group(2)}'",
                                end_line=i,
                                end_column=len(line),
                            )
                        )
    return results
