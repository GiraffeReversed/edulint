from edulint.linting.checkers.basic_checker import ModifiedListener
from edulint.linting.checkers.utils import get_name

from typing import List, Tuple, Dict
import astroid  # type: ignore
from astroid import nodes as astns
import pytest


def split_n_lines(nodes: List[astns.NodeNG], lines: int) -> Tuple[List[astns.NodeNG], List[astns.NodeNG]]:
    if lines == 0:
        return [], nodes

    consumed_lines = []
    for i, node in enumerate(nodes):
        consumed_lines.append(node)
        if hasattr(node, "body"):
            consumed_lines_rec, result_rec = split_n_lines(node.body, lines - len(consumed_lines))
            consumed_lines += consumed_lines_rec
        else:
            result_rec = []

        if len(consumed_lines) == lines:
            return consumed_lines, result_rec + nodes[i+1:]
    return consumed_lines, []


@pytest.mark.filterwarnings("ignore:The 'Module.doc' attribute")
@pytest.mark.parametrize("program,init_lines,before_types,after_types", [
    ("x = 5", 1, [astns.Assign], []),
    ("""
x = 5
x += 1""", 1, [astns.Assign], [astns.AugAssign]),
    ("""
x = 5
x = 1""", 1, [astns.Assign], [astns.Assign]),
    ("""
x = 5
y = 1
x += 1""", 2, [astns.Assign, astns.Assign], [astns.AugAssign]),
    ("""
for x in range(10):
    x = 1""", 1, [astns.For], [astns.Assign]),
    ("""
for x in range(10):
    for y in range(11):
        x = 1""", 1, [astns.For], [astns.For]),
    ("""
for x in range(10):
    for y in range(11):
        x = 1""", 2, [astns.For, astns.For], [astns.Assign]),
    ("""
for x in range(10):
    x = 1
    for y in range(11):
        x = 1""", 2, [astns.For, astns.Assign], [astns.For]),
    ("""
for x in range(10):
    x = 1
    for y in range(11):
        x = 1""", 1, [astns.For], [astns.Assign, astns.For]),
    ("""
for x in range(10):
    x = 1
    for y in range(11):
        x = 1
    x += 1""", 1, [astns.For], [astns.Assign, astns.For, astns.AugAssign]),
    ("""
for x in range(10):
    x = 1
    for y in range(11):
        x = 1
    x += 1""", 2, [astns.For, astns.Assign], [astns.For, astns.AugAssign]),
    ("""
for x in range(10):
    x = 1
    for y in range(11):
        x = 1
    x += 1""", 3, [astns.For, astns.Assign, astns.For], [astns.Assign, astns.AugAssign]),
    ("""
for x in range(10):
    x = 1
    for y in range(11):
        x = 1
    x += 1""", 4, [astns.For, astns.Assign, astns.For, astns.Assign], [astns.AugAssign]),
])
def test_split_n_lines(program: str, init_lines: int, before_types: List[type], after_types: List[type]):
    module = astroid.parse(program)
    before, after = split_n_lines(module.body, init_lines)

    def compare(nodes: List[astns.NodeNG], node_types: List[type]):
        assert len(nodes) == len(node_types)

        for node, node_type in zip(nodes, node_types):
            assert isinstance(node, node_type)

    compare(before, before_types)
    compare(after, after_types)


@pytest.mark.parametrize("program,init_lines,modified", [
    (["x = 5"], 1, {"x": False}),
    ([
        "x = 5",
        "x += 1"
    ], 1, {"x": True}),
    ([
        "x = 5",
        "x = 1"
    ], 1, {"x": True}),
    ([
        "x = 5",
        "y = 1",
        "x += 1"
    ], 2, {"x": True, "y": False}),
    ([
        "for x in range(10):",
        "    for x in range(11):",
        "        pass"
    ], 1, {"x": True}),
    ([
        "for x in range(10):",
        "    for y in range(11):",
        "        pass"
    ], 1, {"x": False}),
    ([
        "x = 0",
        "def foo():",
        "    global x",
        "    x = 1"
    ], 1, {"x": True}),
    ([
        "x = 0",
        "def foo():",
        "    global x",
        "    x += 1"
    ], 1, {"x": True}),
    ([
        "x = 0",
        "def foo():",
        "    nonlocal x",
        "    x = 1"
    ], 1, {"x": True}),
    ([
        "x = 0",
        "def foo():",
        "    x = 1",
        "    def bar():",
        "        nonlocal x",
        "        x = 2"
    ], 1, {"x": False}),
    ([
        "x = []",
        "def foo():",
        "    x.append(1)"
    ], 1, {"x": True}),
    ([
        "x = []",
        "def foo():",
        "    x[0] = 1"
    ], 1, {"x": True}),
    ([
        "x = None",
        "def foo():",
        "    x.y = 1"
    ], 1, {"x": True}),
    ([
        "x = None",
        "def foo():",
        "    x.y.z = 1"
    ], 1, {"x": True}),
    ([
        "x = None",
        "def foo():",
        "    x[0].y[1].z = 1"
    ], 1, {"x": True}),
    ([
        "x = None",
        "def foo():",
        "    x = []",
        "    x.append(0)"
    ], 1, {"x": False}),
    ([
        "x = None",
        "def foo():",
        "    x, y = [], 0",
        "    x.append(0)"
    ], 1, {"x": False}),
    ([
        "x = None",
        "def foo():",
        "    (x, y) = [], 0",
        "    x.append(0)"
    ], 1, {"x": False}),
    ([
        "x = None",
        "def foo(x):",
        "    x.append(0)"
    ], 1, {"x": False}),
    ([
        "x = None",
        "def foo(x: List[int] = []):",
        "    x.append(0)"
    ], 1, {"x": False}),
])
def test_modified_listener(program: List[str], init_lines: int, modified: Dict[str, bool]):
    module = astroid.parse("\n".join(program))
    before, after = split_n_lines(module.body, init_lines)

    def extract_vars(nodes: List[astns.NodeNG]) -> List[astns.NodeNG]:
        result = []
        for node in nodes:
            if hasattr(node, "target"):
                result.append(node.target)
            if hasattr(node, "targets"):
                result.extend(node.targets)
        return result

    watched = extract_vars(before)
    listener: ModifiedListener = ModifiedListener(watched)
    listener.visit_many(after)
    assert {get_name(n): listener.was_modified(n, allow_definition=False) for n in watched} == modified
