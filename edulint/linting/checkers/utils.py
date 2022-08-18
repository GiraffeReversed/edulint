from typing import Any, TypeVar, Generic, List, Iterable
from astroid import nodes  # type: ignore
import sys
import inspect


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
    return self.combine([child.accept(self) for child in node.get_children()])


for name, obj in inspect.getmembers(nodes, inspect.isclass):
    setattr(BaseVisitor, f"visit_{obj.__name__.lower()}", generic_visit)
