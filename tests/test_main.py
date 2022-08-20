import pytest
from edulint.edulint import main
from os.path import join


def compare_output(monkeypatch, capsys, argv, output):
    monkeypatch.setattr("sys.argv", ["script"] + argv)
    main()
    captured = capsys.readouterr()
    import sys
    print(captured.err, file=sys.stderr)
    assert captured.out == output


@pytest.mark.parametrize("argv,output", [
    ([join("tests", "data", "hello_world.py")], ""),
    (
        [join("tests", "data", "custom_nonpep_assign.py")],
        "tests/data/custom_nonpep_assign.py:1:2: E225 missing whitespace around operator\n"
    ),
    (
        [join("tests", "data", "custom_flake8_pylint.py")],
        "tests/data/custom_flake8_pylint.py:1:0: C0104 Disallowed name \"foo\"\n"
        "tests/data/custom_flake8_pylint.py:2:5: F841 local variable 'a' is assigned to but never used\n"
    ),
])
def test_single_file_stdout(monkeypatch, capsys, argv, output):
    compare_output(monkeypatch, capsys, argv, output)


@pytest.mark.parametrize("argv,output", [
    (
        [join("tests", "data", "hello_world.py"), join("tests", "data", "custom_nonpep_assign.py")],
        "****************** custom_nonpep_assign.py\n"
        "tests/data/custom_nonpep_assign.py:1:2: E225 missing whitespace around operator\n"
    ),
    (
        [join("tests", "data", "custom_nonpep_assign.py"), join("tests", "data", "custom_flake8_pylint.py")],
        "****************** custom_nonpep_assign.py\n"
        "tests/data/custom_nonpep_assign.py:1:2: E225 missing whitespace around operator\n"
        "****************** custom_flake8_pylint.py\n"
        "tests/data/custom_flake8_pylint.py:1:0: C0104 Disallowed name \"foo\"\n"
        "tests/data/custom_flake8_pylint.py:2:5: F841 local variable 'a' is assigned to but never used\n"
    ),
    (
        [join("tests", "data", "custom_flake8_pylint.py"), join("tests", "data", "custom_nonpep_assign.py")],
        "****************** custom_flake8_pylint.py\n"
        "tests/data/custom_flake8_pylint.py:1:0: C0104 Disallowed name \"foo\"\n"
        "tests/data/custom_flake8_pylint.py:2:5: F841 local variable 'a' is assigned to but never used\n"
        "****************** custom_nonpep_assign.py\n"
        "tests/data/custom_nonpep_assign.py:1:2: E225 missing whitespace around operator\n"
    ),
])
def test_multiple_files_stdout(monkeypatch, capsys, argv, output):
    compare_output(monkeypatch, capsys, argv, output)


@pytest.mark.parametrize("argv,output", [
    (
        [join("tests", "data", "custom_nonpep_assign.py"), join("tests", "data", "custom_flake8_pylint_config.py")],
        "****************** custom_nonpep_assign.py\n"
        "tests/data/custom_nonpep_assign.py:1:2: E225 missing whitespace around operator\n"
        "****************** custom_flake8_pylint_config.py\n"
        "tests/data/custom_flake8_pylint_config.py:1:0: C0114 Missing module docstring\n"
        "tests/data/custom_flake8_pylint_config.py:3:0: C0104 Disallowed name \"foo\"\n"
        "tests/data/custom_flake8_pylint_config.py:4:5: F841 local variable 'a' is assigned to but never used\n"
    ),
    (
        [join("tests", "data", "custom_flake8_pylint_config.py"), join("tests", "data", "custom_nonpep_assign.py")],
        "****************** custom_flake8_pylint_config.py\n"
        "tests/data/custom_flake8_pylint_config.py:1:0: C0114 Missing module docstring\n"
        "tests/data/custom_flake8_pylint_config.py:3:0: C0104 Disallowed name \"foo\"\n"
        "tests/data/custom_flake8_pylint_config.py:4:5: F841 local variable 'a' is assigned to but never used\n"
        "****************** custom_nonpep_assign.py\n"
        "tests/data/custom_nonpep_assign.py:1:2: E225 missing whitespace around operator\n"
    ),
])
def test_different_configs(monkeypatch, capsys, argv, output):
    compare_output(monkeypatch, capsys, argv, output)
