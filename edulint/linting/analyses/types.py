from enum import Enum, auto
from functools import reduce
from typing import Optional, List, Union
import operator

from astroid import nodes

from edulint.linting.analyses.data_dependency import get_assigned_expressions
from edulint.linting.checkers.utils import is_builtin, BaseVisitor, get_range_params


class Type(Enum):
    INT = auto()
    FLOAT = auto()
    BOOL = auto()
    STRING = auto()
    LIST = auto()
    TUPLE = auto()
    DICT = auto()
    SET = auto()
    MODULE = auto()

    @staticmethod
    def from_name(type_str: str) -> "Type":
        for type in Type:
            if type.name.lower() == type_str:
                return type
        raise AttributeError(f"no such type as {type_str}")

    def __int__(self):
        return self.value


class MetaTypes(type):
    def __getattr__(cls, key):
        return lambda: Types(Type.from_name(key))


class Types(metaclass=MetaTypes):
    """
    A bitvector of possible types for a value.

    Call, e.g., Types.int() to create a bitvector with only int.
    """

    def __init__(self, t: Optional[Type] = None):
        self.types = (1 << int(t)) if t is not None else 0

    @classmethod
    def _from(cls, int_val: int):
        result = cls.empty()
        result.types = int_val
        return result

    @classmethod
    def empty(cls):
        return cls()

    def __and__(self, other):
        return Types._from(self.types & other.types)

    def __or__(self, other):
        return Types._from(self.types | other.types)

    def __len__(self):
        return self.types.bit_count()

    def has(self, type):
        return ((1 << int(type)) & self.types) > 0

    def has_only(self, types: Union[Type, List[Type]]):
        if isinstance(types, Type):
            types = [types]
        return all(t in types for t in self.get())

    def get(self) -> List[Type]:
        result = []
        for type in Type:
            if self.has(type):
                result.append(type)
        return result

    def any_mutable(self):
        return any(self.has(t) for t in (Type.LIST, Type.SET, Type.DICT))

    def any_container(self):
        return any(self.has(t) for t in (Type.STRING, Type.LIST, Type.TUPLE, Type.SET, Type.DICT))

    def __repr__(self):
        return f"({' | '.join(t.name for t in self.get())})"


BUILTIN_TYPES = {
    "abs": Types.int(),
    "all": Types.bool(),
    "any": Types.bool(),
    "ascii": Types.string(),
    "bin": Types.string(),
    "bool": Types.bool(),
    "callable": Types.bool(),
    "chr": Types.string(),
    "dict": Types.dict(),
    "divmod": Types.tuple(),
    "float": Types.float(),
    "hex": Types.string(),
    "input": Types.string(),
    "int": Types.int(),
    "isinstance": Types.bool(),
    "issubclass": Types.bool(),
    "len": Types.int(),
    "list": Types.list(),
    "max": Types.int() | Types.float(),
    "min": Types.int() | Types.float(),
    "oct": Types.string(),
    "ord": Types.int(),
    "pow": Types.int() | Types.float(),
    "repr": Types.string(),
    "round": Types.int(),
    "set": Types.set(),
    "sorted": Types.list(),
    "str": Types.string(),
    "sum": Types.int() | Types.float(),
    "tuple": Types.tuple(),
}

TYPE_METHOD_TYPES = {
    Type.STRING: {
        "capitalize": Types.string(),
        "casefold": Types.string(),
        "center": Types.string(),
        "count": Types.int(),
        "endswith": Types.bool(),
        "expandtabs": Types.string(),
        "find": Types.int(),
        "format": Types.string(),
        "format_map": Types.string(),
        "index": Types.int(),
        "isalnum": Types.bool(),
        "isalpha": Types.bool(),
        "isascii": Types.bool(),
        "isdecimal": Types.bool(),
        "isdigit": Types.bool(),
        "isidentifier": Types.bool(),
        "islower": Types.bool(),
        "isnumeric": Types.bool(),
        "isprintable": Types.bool(),
        "isspace": Types.bool(),
        "istitle": Types.bool(),
        "isupper": Types.bool(),
        "join": Types.string(),
        "ljust": Types.string(),
        "lower": Types.string(),
        "lstrip": Types.string(),
        "partition": Types.list(),
        "replace": Types.string(),
        "rfind": Types.int(),
        "rindex": Types.int(),
        "rjust": Types.string(),
        "rpartition": Types.list(),
        "rsplit": Types.list(),
        "rstrip": Types.string(),
        "split": Types.list(),
        "splitline": Types.list(),
        "startswith": Types.bool(),
        "strip": Types.string(),
        "swapcase": Types.string(),
        "title": Types.string(),
        "upper": Types.string(),
        "zfill": Types.string(),
    },
    Types.LIST: {  # methods returning None are ignored
        # "append": Types.empty(),
        # "clear": Types.empty(),
        "copy": Types.list(),
        "count": Types.int(),
        # "extend": Types.empty(),
        "index": Types.int(),
        # "insert": Types.empty(),
        "pop": Types.empty(),
        # "remove": Types.empty(),
        # "reverse": Types.empty(),
        # "sort": Types.empty(),
    },
    Types.DICT: {
        "copy": Types.dict(),
        "fromkeys": Types.dict(),
        "get": Types.empty(),
        "items": Types.empty(),
        "keys": Types.empty(),
        "pop": Types.empty(),
        "popitem": Types.empty(),
        "values": Types.empty(),
    },
    Types.TUPLE: {
        "count": Types.int(),
        "index": Types.int(),
    },
    Types.SET: {
        "copy": Types.set(),
        "difference": Types.set(),
        "intersection": Types.set(),
        "isdisjoint": Types.bool(),
        "issubset": Types.bool(),
        "issuperset": Types.bool(),
        "pop": Types.empty(),
        "symmetric_difference": Types.set(),
        "union": Types.set(),
    },
}

MODULE_METHOD_TYPES = {
    "math": {
        "trunc": Types.int(),
        "sqrt": Types.float(),
        "cos": Types.float(),
        "sin": Types.float(),
        "radians": Types.float(),
        "degrees": Types.float(),
    }
}


class TypeVisitor(BaseVisitor[Types]):
    default = Types.empty()

    def combine(self, results: List[Types]) -> Types:
        if not results:
            return Types.empty()
        return reduce(operator.or_, results)

    def __init__(self, init_expr):
        self.visited_exprs = {init_expr}

    def visit_const(self, node: nodes.Const):
        val = node.value
        if isinstance(val, bool):
            return Types.bool()
        if isinstance(val, float):
            return Types.float()
        if isinstance(val, int):
            return Types.int()
        if isinstance(val, str):
            return Types.string()
        return Types.empty()

    def visit_name(self, node: nodes.Name):
        result = Types.empty()
        for assigned in get_assigned_expressions(
            node, include_nodes=[nodes.For, nodes.Comprehension], include_destructuring=True
        ):
            if assigned in self.visited_exprs:
                continue
            self.visited_exprs.add(assigned)
            if isinstance(assigned.parent, (nodes.For, nodes.Comprehension)):
                if get_range_params(assigned) is not None:
                    result |= Types.int()
            else:
                result |= self.visit(assigned)
        return result

    def visit_import(self, _node: nodes.Import):
        return Types.module()

    def visit_importfrom(self, _node: nodes.ImportFrom):
        return Types.module()

    def visit_tuple(self, _node: nodes.Tuple):
        return Types.tuple()

    def visit_list(self, _node: nodes.List):
        return Types.list()

    def visit_listcomp(self, _node: nodes.ListComp):
        return Types.list()

    def visit_dict(self, _node: nodes.Dict):
        return Types.dict()

    def visit_dictcomp(self, _node: nodes.DictComp):
        return Types.dict()

    def visit_set(self, _node: nodes.Set):
        return Types.set()

    def visit_setcomp(self, _node: nodes.SetComp):
        return Types.set()

    def visit_subscript(self, _node: nodes.Subscript):
        return Types.empty()

    def visit_attribute(self, _node: nodes.Attribute):
        return Types.empty()

    def visit_lambda(self, _node: nodes.Lambda):
        return Types.empty()

    def visit_starred(self, _node: nodes.Starred):
        return Types.empty()

    def visit_compare(self, _node: nodes.Compare):
        return Types.bool()

    def visit_boolop(self, _node: nodes.BoolOp):
        return Types.bool()

    def visit_ifexp(self, node: nodes.IfExp):
        return self.visit(node.body) | self.visit(node.orelse)

    def visit_binop(self, node: nodes.BinOp):
        if node.op == "+":
            return self.visit(node.left) | self.visit(node.right)

        if node.op == "-":
            lt = self.visit(node.left)
            rt = self.visit(node.right)
            if (lt | rt).has(Type.SET):
                return Types.set()
            if (lt | rt).has(Type.FLOAT):
                return Types.float()
            if (lt | rt).has(Type.INT):
                return Types.int()
            return Types.empty()

        if node.op == "*":
            return self.visit(node.left)

        if node.op == "/":
            return Types.float()

        if node.op == "//":
            return Types.int()

        if node.op == "%":
            if (self.visit(node.left) | self.visit(node.right)).has(Type.STRING):
                return Types.string()
            return Types.int()

        if node.op == "**":
            if (self.visit(node.left) | self.visit(node.right)).has(Type.FLOAT):
                return Types.float()
            return Types.int()

        if node.op in ("&", "|", "^"):
            lt = self.visit(node.left)
            rt = self.visit(node.right)
            if (lt | rt).has(Type.SET):
                return Types.set()
            if (lt & rt).has(Type.BOOL):
                return Types.bool()
            if (lt | rt).has(Type.INT):
                return Types.int()
            return Types.empty()

        if node.op in ("<<", ">>"):
            return Types.int()

        if node.op == "@":
            return Types.empty()

        assert False, f"unreachable, but {node.op}"

    def visit_unaryop(self, node: nodes.UnaryOp):
        if node.op in ("+", "-"):
            return self.visit(node.operand)

        if node.op == "not":
            return Types.bool()

        if node.op == "~":
            return Types.int()

        assert False, f"unreachable, but {node.op}"

    def visit_call(self, node: nodes.Call):
        func = node.func
        if isinstance(func, nodes.Name):
            if is_builtin(func):
                return BUILTIN_TYPES.get(func.name, Types.empty())
            assigned = list(
                get_assigned_expressions(
                    func, include_nodes=[nodes.ImportFrom], include_destructuring=False
                )
            )
            if len(assigned) == 1 and isinstance(assigned[0], nodes.ImportFrom):
                return MODULE_METHOD_TYPES.get(assigned[0].modname, {}).get(
                    func.name, Types.empty()
                )
            return Types.empty()

        if isinstance(func, nodes.Attribute):
            expr_type = self.visit(func.expr)
            if len(expr_type) != 1:
                return Types.empty()
            expr_type = expr_type.get()[0]
            if expr_type == Type.MODULE:
                return MODULE_METHOD_TYPES.get(func.expr.as_string(), {}).get(
                    func.attrname, Types.empty()
                )
            return TYPE_METHOD_TYPES.get(expr_type, {}).get(func.attrname, Types.empty())

        return Types.empty()


def guess_type(expr: nodes.NodeNG) -> Optional[Types]:
    """Returns possible types for the given expresssion, or None if the type cannot be determined."""
    result = TypeVisitor(expr).visit(expr)
    return result if len(result) > 0 else None
