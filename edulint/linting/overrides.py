from typing import Dict, Set

# when there is:
# "key": overriders
# then if on one line there would be both "key" and some overriders, the "key" would be ignored (ie. overriden by the overriders)

OVERRIDERS = {
    # overriden: { overriders }
    "C0104": {"R6307", "R6609", "F841", "W0613"},
    # C0104=diallowed-name; R6307=use-for-each; R6609=augmenting-assignment
    #                       F841=unused variable; W0613=unused-argument
    "C0103": {"R6307", "R6609", "F841", "W0613"},
    # C0103=invalid-name
    "E225": {"R6609"},
    # E225=missing whitespace around operator
    "R1705": {"R1703", "R6201"},
    # R1705=no-else-return, R1703=simplifiable-if-statement
    "R6610": {"R6608"},
    # R6610=do-not-multiply-mutable, R6608=redundant-arithmetic
    "W0107": {"W0101"},
    # W0107=unnecessary-pass, W0101=unreachable
    "C0201": {"C0206"},
    # C0201=consider-iterating-dictionary, C0206=consider-using-dict-items
    "R6216": {
        "R6211",
        "R6212",
        "R6214",
        "R6215",
        "R6224",
    },  # checkers that might make conflicting or same suggestion as redundant-condition-part
    # R6216=redundant-condition-part, simplifiable-with-abs, redundant-compare-in-condition, using-compare-instead-of-equal, simplifiable-test-by-equals
    "R6213": {"R6216"},
    # R6213=redundant-compare-avoidable-with-max-min, R6216=redundant-condition-part
    "R6221": {"R6222"},
    # R6221=condition-always-false-in-elif, R6222=condition-always-true-or-false
    "R6218": {"R6222"},
    # R6218=condition-always-true-in-elif, R6222=condition-always-true-or-false
    "R6224": {"R6222"},
}


def get_overriders() -> Dict[str, Set[str]]:
    return OVERRIDERS
