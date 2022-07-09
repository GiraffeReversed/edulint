from typing import Dict


explanations: Dict[str, Dict[str, str]] = {
    "W0612": {
        "why": "Having unused variables in code makes the code unnecessarily complicated.",
        "examples": "A solution is to remove the variable, if possible, or rename it to `_`, which is a common"
        "convention for naming unused variables. A variable named `_` should never be used anywhere later in code."
    }
}


def get_explanations() -> Dict[str, Dict[str, str]]:
    return explanations
