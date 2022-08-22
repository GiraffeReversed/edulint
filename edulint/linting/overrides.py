from typing import Dict, Set


OVERRIDERS = {
    "C0104": {"R6101", "R6001", "F841", "W0613"},
    # C0104=diallowed-name; R6101=use-for-each; R6001=augmenting-assignment
    #                       F841=unused variable; W0613=unused-argument
    "C0103": {"R6101", "R6001", "F841", "W0613"},
    # C0103=invalid-name
    "E225": {"R6001"},
    # E225=missing whitespace around operator
    "R1705": {"R1703"},
    # R1705=no-else-return, R1703=simplifiable-if-statement
}


def get_overriders() -> Dict[str, Set[str]]:
    return OVERRIDERS
