from typing import List, Tuple, Set, Iterator

import pytest
import astroid
from astroid import nodes

from edulint.linting.problem import Problem
from edulint.linting.analyses.patcher import run_analyses
from edulint.linting.analyses.data_dependency import get_defs_at
from edulint.linting.analyses.cfg.utils import get_cfg_loc
from test_utils import apply_and_lint

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


def get_line(node: nodes.NodeNG, n: int) -> Iterator[nodes.NodeNG]:
    if (
        n <= node.fromlineno and node.tolineno <= n
        or isinstance(node, (nodes.FunctionDef, nodes.ClassDef)) and n == node.fromlineno
    ):
        return node

    for child in reversed(list(node.get_children())):
        if child.fromlineno <= n and n <= child.tolineno:
            r = get_line(child, n)
            if r is not None:
                return r
    return None


@pytest.mark.parametrize("lines,edges", [
    ([  # 0
        "a = 0",
        "pass"
    ], [("a", 2, {1})]),
    ([  # 1
        "A = 0",
        "def foo():",  # 2
        "    global A",
        "    A = 1",
        "",
        "def bar(c):",  # 6
        "    global A",
        "    A = 2",
        "    if c:",
        "        foo()",
        "",
        "def car(c):",  # 12
        "    bar()",
        "    pass",
    ], [("A", 13, {1, 4, 8}), ("A", 14, {4, 8})]),
    ([  # 2
        "def foo():",
        "    A = 0",
        "    def bar():",
        "        pass",
        "    pass"
    ], [("A", 4, {2})]),
    ([  # 3
        "def foo(c):",
        "    A = 0",
        "    def bar():",
        "        pass",
        "    if c:",
        "        A = 1",
    ], [("A", 4, {2, 6})]),
    ([  # 4
        "A = 0",
        "def foo():",
        "    global A",
        "    A = 1",
        "",
        "def bar():",
        "    global A",
        "    A = 2",
        "",
        "funs = [foo, bar]",
        "funs[0]()",
        "pass",
    ], [("A", 12, {4, 8})]),
    ([  # 5
        "A = 0",
        "def foo():",
        "    pass",
        "def bar():",
        "    global A",
        "    A = 1",
        "(foo if True else bar)()",
        "foo()",
        "A = 2",
    ], [("A", 3, {1, 6})]),
    ([  # 6
        "def foo(c, arr):",
        "    A = 0",
        "    (max if c else min)(arr)",
        "    pass",
    ], [("A", 4, {2})]),
    ([  # 7
        "A = 0",
        "def foo(c, arr):",
        "    (max if c else min)(arr)",
        "    pass",
    ], [("A", 4, {1})]),
    ([  # 8
        "A = 0",
        "def foo():",
        "    global A",
        "    pass",
        "    A = 1",
        "    foo()"
    ], [("A", 4, {1, 5})]),
    ([  # 9
        "A = 0",
        "def foo():",  # 2
        "    global A",
        "    pass",
        "    A = 1",
        "    bar()",
        "def bar():",  # 7
        "    global A",
        "    A = 2",
        "    foo()",
    ], [("A", 4, {1, 5, 9})]),
    ([  # 10
        "A = 0",
        "def foo(c):",  # 2
        "    global A",
        "    pass",
        "    A = 1",
        "    if c:",
        "        bar(c)",
        "def bar(c):",  # 8
        "    global A",
        "    A = 2",
        "    if c:",
        "        foo(c)",
    ], [("A", 4, {1, 5, 10})]),
])
def test_data_dependency_defs_at(lines: List[str], edges: List[Tuple[str, int, Set[int]]]) -> None:
    code = "\n".join(lines)
    ast = astroid.parse(code)
    run_analyses(ast)

    for varname, at_line, expected_def_lines in edges:
        node = get_line(ast, at_line)
        assert node is not None

        received_def_lines = set()
        for event in get_defs_at(node, varname):
            if event.var.name == varname:
                received_def_lines.add(event.node.fromlineno)

        assert expected_def_lines == received_def_lines


@pytest.mark.parametrize("lines,edges", [
    ([  # 0
        "a = 0",
        "print(a)"
    ], [("a", 1, {2})]),
    ([  # 1
        "def foo(c):",
        "    a = 0",
        "    if c:",
        "        a = 1",
        "    print(a)",
    ], [("a", 2, {5}), ("a", 4, {5})]),
    ([  # 2
        "A = 0",
        "def foo(c):",
        "    global A",
        "    if c:",
        "        A = 1",
        "    print(A)"
    ], [("A", 1, {6}), ("A", 5, {6})]),
    ([  # 3
        "def foo():",
        "    pass",
        "foo()",
        "",
        "def foo():",
        "    pass",
        "foo()"
    ], [("foo", 1, {3}), ("foo", 5, {7})]),
    ([  # 4
        "def foo():",
        "    pass",
        "foo()",
        "",
        "def foo():",
        "    foo()",
        "foo()"
    ], [("foo", 1, {3, 6}), ("foo", 5, {6, 7})]),  # 6 in first is over-approximation
    ([  # 5
        "def foo():",
        "    foo()",
        "",
        "def foo():",
        "    foo()",
    ], [("foo", 4, {2, 5})]),  # 2 is over-approximation
    ([  # 6
        "def foo():",
        "    foo()",
        "foo()",
        "",
        "def foo():",
        "    foo()",
    ], [("foo", 1, {2, 3, 6}), ("foo", 5, {2, 6})]),  # 6 in first, 2 in second is over-approximation
    ([  # 7
        "A = 0",
        "def foo():",  # 2
        "    global A",
        "    A = 1",
        "",
        "def bar():",  # 6
        "    global A",
        "    A = 2",
        "",
        "def car():",  # 10
        "    global A",
        "    A = 3",
        "",
        "def fun():",  # 14
        "    B = 0",
        "    funs = [foo, bar]",
        "    funs[0]()",
        "    print(A)",
        "    print(B)",
        "    foo()",
        "    print(A)"
    ], [("A", 1, set()), ("A", 4, {18, 21}), ("A", 8, {18, 21}), ("A", 12, {18, 21}), ("B", 15, {19})]),  # 21 in all but second is over-approximation
    ([  # 8
        "A = 0",
        "def foo():",  # 2
        "    global A",
        "    pass",
        "    A = 1",
        "    bar()",
        "def bar():",  # 7
        "    global A",
        "    A = 2",
        "    foo()",
    ], [("foo", 2, {10}), ("bar", 7, {6})]),
    ([  # 9
        "A = 0",
        "def foo(c):",  # 2
        "    global A",
        "    print(A)",
        "    A = 1",
        "    if c:",
        "        bar()",
        "def bar(c):",  # 8
        "    global A",
        "    print(A)",
        "    A = 2",
        "    if c:",
        "        foo()",
    ], [("A", 1, {4, 10}), ("A", 5, {4, 10}), ("A", 11, {4, 10})]),
])
def test_data_dependency_defs_uses(lines: List[str], edges: List[Tuple[str, int, Set[int]]]) -> None:
    code = "\n".join(lines)
    ast = astroid.parse(code)
    assert ast
    run_analyses(ast)

    for varname, def_line, expected_use_lines in edges:
        def_node = get_line(ast, def_line)
        assert def_node is not None

        received_use_lines = set()
        var_events = list(get_cfg_loc(def_node).var_events.for_name(varname))
        assert len(var_events) > 0
        for _var, event in var_events:
            for use in event.uses:
                received_use_lines.add(use.node.fromlineno)

        assert expected_use_lines == received_use_lines
