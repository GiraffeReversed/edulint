import pytest
from edulint.linting.problem import Problem
from test_utils import apply_and_lint
from typing import List


@pytest.mark.parametrize("filename,expected_output", [
    ("cf_1166_c_4.py", []),
    ("ksi_17_513_aacd.py", []),
    # TODO report identical functions
    ("pronto_jawless_seismic_hefty.py", []),
])
def test_cfg(filename: str, expected_output: List[Problem]) -> None:
    apply_and_lint(
        filename,
        [],
        expected_output
    )


@pytest.mark.parametrize("filename,expected_output", [
    ("24dc5b19.py", []),
])
def test_variable_scopes(filename: str, expected_output: List[Problem]) -> None:
    apply_and_lint(
        filename,
        [],
        expected_output
    )
