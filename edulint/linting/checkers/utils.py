from typing import Any, TypeVar, Generic, List, Iterable, Union, Optional, Tuple, cast
from astroid import nodes  # type: ignore
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


def get_range_params(node: nodes.NodeNG) -> Optional[Tuple[nodes.NodeNG, nodes.NodeNG, nodes.NodeNG]]:
    if not isinstance(node, nodes.Call) or node.func.as_string() != "range":
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
        assert False, "unreachable" + node.op

    return None
