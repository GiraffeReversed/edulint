from typing import Any, TypeVar, Generic, List, Iterable, Union, Optional, Tuple, cast
from astroid import nodes, Uninferable  # type: ignore
import sys
import inspect
from pylint.checkers import utils  # type: ignore


def eprint(*args: Any, **kwargs: Any) -> None:
    print(*args, file=sys.stderr, **kwargs)


T = TypeVar("T")


class BaseVisitor(Generic[T]):
    default: T = None  # type: ignore

    @classmethod
    def combine(cls, results: List[T]) -> T:
        if not results:
            return cls.default  # type: ignore
        return results[-1]

    def visit(self, node: nodes.NodeNG) -> T:
        return node.accept(self)  # type: ignore

    def visit_many(self, nodes: Iterable[nodes.NodeNG]) -> T:
        return self.combine([self.visit(node) for node in nodes])


def generic_visit(self: BaseVisitor[T], node: nodes.NodeNG) -> T:
    return self.combine([self.visit(child) for child in node.get_children()])


for name, obj in inspect.getmembers(nodes, inspect.isclass):
    setattr(BaseVisitor, f"visit_{obj.__name__.lower()}", generic_visit)


# rightfully stolen from
# https://github.com/PyCQA/pylint/blob/ca80f03a43bc39e4cc2c67dc99817b3c9f13b8a6/pylint/checkers/refactoring/recommendation_checker.py
def is_builtin(node: nodes.NodeNG, function: Optional[str] = None) -> bool:
    inferred = utils.safe_infer(node)
    if not inferred:
        return False
    return utils.is_builtin_object(inferred) and function is None or inferred.name == function


def is_multi_assign(node: nodes.NodeNG) -> bool:
    return hasattr(node, "targets")


def is_assign(node: nodes.NodeNG) -> bool:
    return hasattr(node, "target")


def is_any_assign(node: nodes.NodeNG) -> bool:
    return is_assign(node) or is_multi_assign(node)


def get_assigned_to(node: nodes.NodeNG) -> List[nodes.NodeNG]:
    if is_multi_assign(node):
        return cast(List[nodes.NodeNG], node.targets)
    if is_assign(node):
        return [node.target]
    return []


Named = Union[nodes.Name, nodes.Attribute, nodes.AssignName]


def is_named(node: nodes.NodeNG) -> bool:
    return hasattr(node, "name") or hasattr(node, "attrname")


def get_name(node: Named) -> str:
    return node.as_string()


def get_range_params(
    node: nodes.NodeNG,
) -> Optional[Tuple[nodes.NodeNG, nodes.NodeNG, nodes.NodeNG]]:
    if (
        not isinstance(node, nodes.Call)
        or node.func.as_string() != "range"
        or len(node.args) < 1
        or len(node.args) > 3
    ):
        return None

    default_start = nodes.Const(0)
    default_step = nodes.Const(1)

    if len(node.args) == 1:
        return default_start, node.args[0], default_step

    if len(node.args) == 2:
        return node.args[0], node.args[1], default_step

    if len(node.args) == 3:
        return node.args[0], node.args[1], node.args[2]

    assert False, "unreachable"


def get_const_value(node: nodes.NodeNG) -> Any:
    if isinstance(node, nodes.Const):
        return node.value

    if isinstance(node, nodes.UnaryOp) and isinstance(node.operand, nodes.Const):
        if node.op == "+":
            return node.operand.value
        if node.op == "-":
            return -node.operand.value
        if node.op == "not":
            return not node.operand.value
        if node.op == "~":
            return ~node.operand.value
        assert False, "unreachable" + node.op

    return None


def infer_to_value(node: nodes.NodeNG) -> Optional[nodes.NodeNG]:
    if isinstance(node, nodes.Name):
        inferred = utils.safe_infer(node)
        return None if inferred is Uninferable else inferred

    if isinstance(
        node,
        (
            nodes.Const,
            nodes.List,
            nodes.Set,
            nodes.Dict,
            nodes.ListComp,
            nodes.DictComp,
            nodes.Call,
        ),
    ):
        return node

    return None


def is_parents_elif(node: nodes.If) -> bool:
    parent = node.parent
    return isinstance(parent, nodes.If) and parent.has_elif_block() and parent.orelse[0] == node


def get_lines_between(first: nodes.NodeNG, last: nodes.NodeNG, including_last: bool) -> int:
    assert first.fromlineno <= last.fromlineno

    if including_last:
        return last.tolineno - first.fromlineno + 1
    return last.fromlineno - first.fromlineno


def is_main_block(statement: nodes.If) -> bool:
    """
    Return whether or not <statement> is the main block.
    """
    return (
        isinstance(statement, nodes.If)
        and isinstance(statement.test, nodes.Compare)
        and isinstance(statement.test.left, nodes.Name)
        and isinstance(statement.test.left, nodes.Name)
        and statement.test.left.name == "__name__"
        and len(statement.test.ops) == 1
        and statement.test.ops[0][0] == "=="
        and isinstance(statement.test.ops[0][1], nodes.Const)
        and statement.test.ops[0][1].value == "__main__"
    )


def is_block_comment(stmt: nodes.NodeNG) -> bool:
    return (
        isinstance(stmt, nodes.Expr)
        and isinstance(stmt.value, nodes.Const)
        and isinstance(stmt.value.value, str)
    )


def get_statements_count(
    node: Union[nodes.NodeNG, List[nodes.NodeNG]], include_defs: bool, include_name_main: bool
) -> int:
    def count(nodes: List[nodes.NodeNG]) -> int:
        return sum(get_statements_count(node, include_defs, include_name_main) for node in nodes)

    if isinstance(node, list):
        return count(node)

    if isinstance(node, (nodes.ClassDef, nodes.FunctionDef)):
        return 1 + count(node.body) if include_defs else 0

    if isinstance(node, (nodes.Import, nodes.ImportFrom)):
        return 1 if include_defs else 0

    if isinstance(node, (nodes.For, nodes.While, nodes.If)):
        if is_main_block(node) and not include_name_main:
            return 0
        return 1 + count(node.body) + count(node.orelse)

    if isinstance(node, nodes.Module):
        return count(node.body)

    if isinstance(node, nodes.TryExcept):
        return 2 + count(node.body) + sum(count(h.body) for h in node.handlers) + count(node.orelse)

    if isinstance(node, nodes.TryFinally):
        return 2 + count(node.body) + count(node.finalbody)

    if isinstance(node, nodes.With):
        return 1 + count(node.body)

    return 1
