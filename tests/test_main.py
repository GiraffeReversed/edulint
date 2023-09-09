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


@pytest.mark.parametrize(
    "argv,output",
    [
        ([join("tests", "data", "hello_world.py")], ""),
        (
            [join("tests", "data", "custom_nonpep_assign.py")],
            f"{join('tests', 'data', 'custom_nonpep_assign.py')}:1:0: C0103 Constant name \"a\" doesn't conform to UPPER_CASE naming style [default]\n"
            f"{join('tests', 'data', 'custom_nonpep_assign.py')}:1:2: E225 missing whitespace around operator [default]\n",
        ),
        (
            [join("tests", "data", "custom_flake8_pylint.py")],
            f'{join("tests", "data", "custom_flake8_pylint.py")}:1:0: C0104 Disallowed name "foo" [default]\n'
            f"{join('tests', 'data', 'custom_flake8_pylint.py')}:2:5: F841 local variable 'a' is assigned to but never used [default]\n",
        ),
    ],
)
def test_single_file_stdout(monkeypatch, capsys, argv, output):
    compare_output(monkeypatch, capsys, argv, output)


@pytest.mark.parametrize(
    "argv,output",
    [
        (
            [
                join("tests", "data", "hello_world.py"),
                join("tests", "data", "custom_nonpep_assign.py"),
            ],
            "****************** custom_nonpep_assign.py\n"
            f'{join("tests", "data", "custom_nonpep_assign.py")}:1:0: C0103 Constant name "a" doesn\'t conform to UPPER_CASE naming style [default]\n'
            f"{join('tests', 'data', 'custom_nonpep_assign.py')}:1:2: E225 missing whitespace around operator [default]\n",
        ),
        (
            [
                join("tests", "data", "custom_nonpep_assign.py"),
                join("tests", "data", "custom_flake8_pylint.py"),
            ],
            "****************** custom_nonpep_assign.py\n"
            f'{join("tests", "data", "custom_nonpep_assign.py")}:1:0: C0103 Constant name "a" doesn\'t conform to UPPER_CASE naming style [default]\n'
            f"{join('tests', 'data', 'custom_nonpep_assign.py')}:1:2: E225 missing whitespace around operator [default]\n"
            "****************** custom_flake8_pylint.py\n"
            f'{join("tests", "data", "custom_flake8_pylint.py")}:1:0: C0104 Disallowed name "foo" [default]\n'
            f"{join('tests', 'data', 'custom_flake8_pylint.py')}:2:5: F841 local variable 'a' is assigned to but never used [default]\n",
        ),
        (
            [
                join("tests", "data", "custom_flake8_pylint.py"),
                join("tests", "data", "custom_nonpep_assign.py"),
            ],
            "****************** custom_flake8_pylint.py\n"
            f'{join("tests", "data", "custom_flake8_pylint.py")}:1:0: C0104 Disallowed name "foo" [default]\n'
            f"{join('tests', 'data', 'custom_flake8_pylint.py')}:2:5: F841 local variable 'a' is assigned to but never used [default]\n"
            "****************** custom_nonpep_assign.py\n"
            f'{join("tests", "data", "custom_nonpep_assign.py")}:1:0: C0103 Constant name "a" doesn\'t conform to UPPER_CASE naming style [default]\n'
            f"{join('tests', 'data', 'custom_nonpep_assign.py')}:1:2: E225 missing whitespace around operator [default]\n",
        ),
    ],
)
def test_multiple_files_stdout(monkeypatch, capsys, argv, output):
    compare_output(monkeypatch, capsys, argv, output)


@pytest.mark.parametrize(
    "argv,output",
    [
        (
            [
                join("tests", "data", "custom_nonpep_assign.py"),
                join("tests", "data", "custom_flake8_pylint_config.py"),
            ],
            "****************** custom_nonpep_assign.py\n"
            f'{join("tests", "data", "custom_nonpep_assign.py")}:1:0: C0103 Constant name "a" doesn\'t conform to UPPER_CASE naming style [default]\n'
            f"{join('tests', 'data', 'custom_nonpep_assign.py')}:1:2: E225 missing whitespace around operator [default]\n"
            "****************** custom_flake8_pylint_config.py\n"
            f"{join('tests', 'data', 'custom_flake8_pylint_config.py')}:1:0: C0114 Missing module docstring [in-file]\n"
            f'{join("tests", "data", "custom_flake8_pylint_config.py")}:3:0: C0104 Disallowed name "foo" [default]\n'
            f"{join('tests', 'data', 'custom_flake8_pylint_config.py')}:4:5: F841 local variable 'a' is assigned to but never used [default]\n",
        ),
        (
            [
                join("tests", "data", "custom_flake8_pylint_config.py"),
                join("tests", "data", "custom_nonpep_assign.py"),
            ],
            "****************** custom_flake8_pylint_config.py\n"
            f"{join('tests', 'data', 'custom_flake8_pylint_config.py')}:1:0: C0114 Missing module docstring [in-file]\n"
            f'{join("tests", "data", "custom_flake8_pylint_config.py")}:3:0: C0104 Disallowed name "foo" [default]\n'
            f"{join('tests', 'data', 'custom_flake8_pylint_config.py')}:4:5: F841 local variable 'a' is assigned to but never used [default]\n"
            "****************** custom_nonpep_assign.py\n"
            f'{join("tests", "data", "custom_nonpep_assign.py")}:1:0: C0103 Constant name "a" doesn\'t conform to UPPER_CASE naming style [default]\n'
            f"{join('tests', 'data', 'custom_nonpep_assign.py')}:1:2: E225 missing whitespace around operator [default]\n",
        ),
    ],
)
def test_different_configs(monkeypatch, capsys, argv, output):
    compare_output(monkeypatch, capsys, argv, output)


@pytest.mark.parametrize(
    "argv,output",
    [
        (
            f"{join('tests', 'data', 'custom_flake8_pylint.py')} -o pylint=--enable=missing-module-docstring".split(),
            f"{join('tests', 'data', 'custom_flake8_pylint.py')}:1:0: C0114 Missing module docstring [cmd]\n"
            f'{join("tests", "data", "custom_flake8_pylint.py")}:1:0: C0104 Disallowed name "foo" [default]\n'
            f"{join('tests', 'data', 'custom_flake8_pylint.py')}:2:5: F841 local variable 'a' is assigned to but never used [default]\n",
        ),
        (
            f"{join('tests', 'data', 'custom_flake8_pylint.py')} -o=pylint=--enable=missing-module-docstring".split(),
            f"{join('tests', 'data', 'custom_flake8_pylint.py')}:1:0: C0114 Missing module docstring [cmd]\n"
            f'{join("tests", "data", "custom_flake8_pylint.py")}:1:0: C0104 Disallowed name "foo" [default]\n'
            f"{join('tests', 'data', 'custom_flake8_pylint.py')}:2:5: F841 local variable 'a' is assigned to but never used [default]\n",
        ),
        (
            f"{join('tests', 'data', 'custom_flake8_pylint.py')} --option pylint=--enable=missing-module-docstring".split(),
            f"{join('tests', 'data', 'custom_flake8_pylint.py')}:1:0: C0114 Missing module docstring [cmd]\n"
            f'{join("tests", "data", "custom_flake8_pylint.py")}:1:0: C0104 Disallowed name "foo" [default]\n'
            f"{join('tests', 'data', 'custom_flake8_pylint.py')}:2:5: F841 local variable 'a' is assigned to but never used [default]\n",
        ),
        (
            f"{join('tests', 'data', 'custom_flake8_pylint.py')} --option=pylint=--enable=missing-module-docstring".split(),
            f"{join('tests', 'data', 'custom_flake8_pylint.py')}:1:0: C0114 Missing module docstring [cmd]\n"
            f'{join("tests", "data", "custom_flake8_pylint.py")}:1:0: C0104 Disallowed name "foo" [default]\n'
            f"{join('tests', 'data', 'custom_flake8_pylint.py')}:2:5: F841 local variable 'a' is assigned to but never used [default]\n",
        ),
        (
            f"{join('tests', 'data', 'custom_flake8_pylint.py')} "
            "-o pylint=--enable=missing-module-docstring "
            "-o pylint=--disable=C0104".split(),
            f"{join('tests', 'data', 'custom_flake8_pylint.py')}:1:0: C0114 Missing module docstring [cmd]\n"
            f"{join('tests', 'data', 'custom_flake8_pylint.py')}:2:5: F841 local variable 'a' is assigned to but never used [default]\n",
        ),
        (
            [
                join("tests", "data", "custom_flake8_pylint.py"),
                "-o",
                "pylint=--enable=missing-module-docstring pylint=--disable=C0104",
            ],
            f"{join('tests', 'data', 'custom_flake8_pylint.py')}:1:0: C0114 Missing module docstring [cmd]\n"
            f"{join('tests', 'data', 'custom_flake8_pylint.py')}:2:5: F841 local variable 'a' is assigned to but never used [default]\n",
        ),
    ],
)
def test_passing_cmd_args(monkeypatch, capsys, argv, output):
    compare_output(monkeypatch, capsys, argv, output)


@pytest.mark.parametrize("argv,output", [([join("tests", "data", "custom_swap.py")], "")])
def test_ib111_week(monkeypatch, capsys, argv, output):
    compare_output(monkeypatch, capsys, argv, output)
