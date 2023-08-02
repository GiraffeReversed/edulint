# Some modifications are based on good ideas from Thonny
# https://raw.githubusercontent.com/thonny/thonny/master/thonny/plugins/pylint/
# tho_xpln > msg_xpln


def make_explanation_more_friedly(explanation: str) -> str:
    replace_prefixes = {
        "Used when an ": "It looks like the ",
        "Used when a ": "It looks like the ",
        "Used when ": "It looks like ",
        "Emitted when an ": "It looks like the ",
        "Emitted when a ": "It looks like the ",
        "Emitted when ": "It looks like ",
    }

    for prefix, replacement in replace_prefixes.items():
        if explanation.startswith(prefix):
            explanation = replacement + explanation[len(prefix) :]
            break

    return explanation
