import pytest
from edulint.options import Option
from edulint.config.arg import Arg
from edulint.linting.problem import Problem
from utils import lazy_problem, apply_and_lint, create_apply_and_lint
from typing import List


class TestShort:
    @pytest.mark.parametrize("lines,expected_output", [
        ([
            "if x > y:",
            "    print('foo')",
            "elif x <= y:",
            "    print('bar')"
        ], [
            lazy_problem().set_line(3).set_code("R6611")
        ]),
    ])
    def test_short_custom(self, lines: List[str], expected_output: List[Problem]) -> None:
        create_apply_and_lint(
            lines,
            [Arg(Option.PYLINT, "--disable=all"),
             Arg(Option.PYLINT, "--enable=short-problems"),
             Arg(Option.NO_FLAKE8, "on")],
            expected_output
        )

    @pytest.mark.parametrize("filename,expected_output", [
        ("010666-prime.py", [
            lazy_problem().set_code("R6604").set_line(12).set_text("Do not use while loop with else."),
            lazy_problem().set_code("R6609").set_line(15).set_text("Use augmenting assignment: 'i += 1'"),
        ]),
        ("012889-pythagorean.py", [
            lazy_problem().set_code("R6602").set_line(23).set_text("Use integral division //."),
            lazy_problem().set_code("R6602").set_line(24),
            lazy_problem().set_code("R6602").set_line(25),
        ]),
        ("014290-coins.py", [
            lazy_problem().set_code("R6608").set_line(27).set_text("Redundant arithmetic: 1 * (value // 1)")
        ]),
        ("014494-next.py", [
            lazy_problem().set_code("R6602").set_line(5).set_text("Use integral division //."),
            lazy_problem().set_code("R6608").set_line(16).set_text("Redundant arithmetic: number**1"),
        ]),
        ("014661-p5_fibsum.py", [
            lazy_problem().set_code("R6609").set_line(15),
            lazy_problem().set_code("R6609").set_line(18),
            lazy_problem().set_code("R6609").set_line(19),
            lazy_problem().set_code("R6609").set_line(20),
            lazy_problem().set_code("R6611").set_line(23).set_text("Use else instead of elif."),
            lazy_problem().set_code("R6609").set_line(24),

        ]),
        ("017667-prime.py", [
            lazy_problem().set_code("R6604").set_line(6).set_text("Do not use for loop with else.")
        ]),
        ("022859-digit_sum.py", [
            lazy_problem().set_code("R6601").set_line(20)
            .set_text("Use lst.append(number % 7) instead of lst += [number % 7].")
        ]),
        ("024042-cards.py", [
            lazy_problem().set_code("R6609").set_line(9).set_text("Use augmenting assignment: 'number //= 10'")
        ]),
        ("024180-delete.py", [
            lazy_problem().set_code("R6606").set_line(7)
            .set_text("Remove the for loop, as it makes only one iteration.")
        ]),
        ("024233-cards.py", [
            lazy_problem().set_code("R6608").set_line(22).set_text("Redundant arithmetic: 0 + number"),
            lazy_problem().set_code("R6608").set_line(42).set_text("Redundant arithmetic: 0 + number")
        ]),
        ("024371-cards.py", [
            lazy_problem().set_code("R6606").set_line(12).set_text("Remove the for loop, as it makes no iterations.")
        ]),
        ("024371-workdays.py", [
            lazy_problem().set_code("R6606").set_line(29)
            .set_text("Remove the for loop, as it makes only one iteration."),
            lazy_problem().set_code("R6608").set_line(30).set_text("Redundant arithmetic: i + 0"),
        ]),
        ("024491-cards.py", [
            lazy_problem().set_code("R6606").set_line(86)
            .set_text("Remove the for loop, as it makes only one iteration.")
        ]),
        ("024657-bisection.py", [
            lazy_problem().set_code("R6608").set_line(6).set_text("Redundant arithmetic: 0 - eps"),
            lazy_problem().set_code("R6608").set_line(6).set_text("Redundant arithmetic: 0 + eps"),
            lazy_problem().set_code("R6608").set_line(8).set_text("Redundant arithmetic: 0 - eps"),
            lazy_problem().set_code("R6608").set_line(10).set_text("Redundant arithmetic: 0 + eps"),
            lazy_problem().set_code("R6608").set_line(12).set_text("Redundant arithmetic: 0 + eps"),
            lazy_problem().set_code("R6608").set_line(14).set_text("Redundant arithmetic: 0 + eps"),
        ]),
        ("032630-concat.py", [
            lazy_problem().set_code("R6608").set_line(5).set_text("Redundant arithmetic: [0] * 0")
        ]),
        ("041630-ipv4.py", [
            lazy_problem().set_code("R6603").set_line(15).set_text("Use isdecimal to test if string contains a number.")
        ]),
        ("044834-ipv4.py", [
            lazy_problem().set_code("R6603").set_line(15).set_text("Use isdecimal to test if string contains a number.")
        ]),
        ("064633-p4_histogram.py", [
            lazy_problem().set_code("R6611").set_line(35).set_text("Use else instead of elif.")
        ]),
        ("085286-p1_count.py", [
            lazy_problem().set_code("R6611").set_line(27).set_text("Use else instead of elif."),
            lazy_problem().set_code("R6612").set_line(30).set_text("Unreachable else."),
            lazy_problem().set_code("R6611").set_line(41).set_text("Use else instead of elif."),
            lazy_problem().set_code("R6612").set_line(44).set_text("Unreachable else."),
        ]),
        ("104174-ipv4_restore.py", [
            lazy_problem().set_code("R6610").set_line(38).set_text("Do not multiply list with mutable content.")
        ]),
        ("hw14358.py", [
            lazy_problem().set_code("R6609").set_line(29).set_text("Use augmenting assignment: 'result -= element'"),
            lazy_problem().set_code("R6609").set_line(31).set_text("Use augmenting assignment: 'b += 1'"),
            lazy_problem().set_code("R6609").set_line(34).set_text("Use augmenting assignment: 'a += 1'"),
            lazy_problem().set_code("R6608").set_line(44).set_text("Redundant arithmetic: num // num"),
            lazy_problem().set_code("R6609").set_line(50).set_text("Use augmenting assignment: 'count += 1'"),
            lazy_problem().set_code("R6609").set_line(51).set_text("Use augmenting assignment: 'number //= n'"),
            lazy_problem().set_code("R6609").set_line(53).set_text("Use augmenting assignment: 'primes += 1'"),
            lazy_problem().set_code("R6609").set_line(54),
            lazy_problem().set_code("R6609").set_line(56),
            lazy_problem().set_code("R6609").set_line(57),
        ]),
        ("hw34328.py", [
            lazy_problem().set_code("R6608").set_line(79).set_text("Redundant arithmetic: '' + str(count)")
        ]),
        ("hw34451.py", [
            lazy_problem().set_code("R6607").set_line(44)
            .set_text("Use exponentiation instead of repeated muliplication in i * i * i."),
            lazy_problem().set_code("R6607").set_line(47)
            .set_text("Use exponentiation instead of repeated muliplication in i * i * i."),
            lazy_problem().set_code("R6607").set_line(63)
            .set_text("Use exponentiation instead of repeated muliplication in i * i * i."),
            lazy_problem().set_code("R6607").set_line(66)
            .set_text("Use exponentiation instead of repeated muliplication in i * i * i."),
        ]),
        ("hw35219.py", [
            lazy_problem().set_code("R6601").set_line(34)
            .set_text("Use coords_cw.append((-y, x)) instead of coords_cw += [(-y, x)]."),
            lazy_problem().set_code("R6601").set_line(41)
            .set_text("Use coords_ccw.append((y, -x)) instead of coords_ccw += [(y, -x)]."),
            lazy_problem().set_code("R6610").set_line(46).set_text("Do not multiply list with mutable content.")
        ]),
        ("hw45208.py", [
            lazy_problem().set_code("R6605").set_line(32),
            lazy_problem().set_code("R6611").set_line(45),
        ]),
        ("m2630.py", [
            lazy_problem().set_code("R6608").set_line(59).set_text("Redundant arithmetic: [0] * 0"),
            lazy_problem().set_code("R6608").set_line(79).set_text("Redundant arithmetic: num //= num"),
            lazy_problem().set_code("R6608").set_line(83).set_text("Redundant arithmetic: num //= num"),
            lazy_problem().set_code("R6608").set_line(86).set_text("Redundant arithmetic: num //= num"),
            lazy_problem().set_code("R6608").set_line(97).set_text("Redundant arithmetic: position * 1"),
        ]),
        ("m2650.py", [
            lazy_problem().set_code("R6609").set_line(11),
            lazy_problem().set_code("R6609").set_line(41),
            lazy_problem().set_code("R6609").set_line(44),
            lazy_problem().set_code("R6605").set_line(84).set_text("Use elif."),
        ]),
        ("m5435.py", [
            lazy_problem().set_code("R6609").set_line(7),
            lazy_problem().set_code("R6605").set_line(9).set_text("Use elif."),
            lazy_problem().set_code("R6608").set_line(53).set_text("Redundant arithmetic: valid += 0"),
            lazy_problem().set_code("R6608").set_line(64).set_text("Redundant arithmetic: valid += 0"),
        ]),
    ])
    def test_short_files(self, filename: str, expected_output: List[Problem]) -> None:
        apply_and_lint(
            filename,
            [
                Arg(Option.NO_FLAKE8, "on"),
                Arg(Option.PYLINT, "--disable=all"),
                Arg(Option.PYLINT, "--enable=short-problems")
            ],
            expected_output
        )
