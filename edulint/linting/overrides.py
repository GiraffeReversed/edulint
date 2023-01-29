from typing import Dict, Set


OVERRIDERS = {
    "C0104": {"R6101", "R6609", "F841", "W0613"},
    # C0104=diallowed-name; R6101=use-for-each; R6609=augmenting-assignment
    #                       F841=unused variable; W0613=unused-argument
    "C0103": {"R6101", "R6609", "F841", "W0613"},
    # C0103=invalid-name
    "E225": {"R6609"},
    # E225=missing whitespace around operator
    "R1705": {"R1703", "R6201"},
    # R1705=no-else-return, R1703=simplifiable-if-statement
    "R6610": {"R6608"},
    # R6610=do-not-multiply-mutable, R6608=redundant-arithmetic
}


def get_overriders() -> Dict[str, Set[str]]:
    return OVERRIDERS
