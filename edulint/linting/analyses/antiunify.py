from typing import Dict, Union, Tuple, List, Any, Iterator
import copy

from astroid import nodes

from edulint.linting.checkers.utils import eprint


subitution = Dict[str, Union[nodes.NodeNG, Tuple[str, nodes.NodeNG]]]


class AunifyVar(nodes.Name):
    def __init__(self, name: str):
        self.name = name.upper()
        self.parent = None
        self.lineno = 0
        self.subs = []

    def __repr__(self):
        return self.name

    def accept(self, visitor):
        return getattr(visitor, "visit_name")(self)

    def isdigit(self):
        return False

    def __len__(self):
        return 1

    def __str__(self):
        return self.name

    def replace(self, old, new):
        return self.name.replace(old, new)


def _to_list(val):
    return val if isinstance(val, list) else [val]


class Antiunify:
    __num = 0

    def _get_new_avar(self, extra: str = None):
        self.__num += 1
        return AunifyVar(f"id_{self.__num}{('_' + extra) if extra is not None else ''}")

    def _new_aunifier(self, lt: nodes.NodeNG, rt: nodes.NodeNG, extra: str = None):
        avar = self._get_new_avar(extra)
        avar.subs = [lt, rt]
        return avar, [avar]

    def _aunify_consts(self, lt: Any, rt: Any):
        if lt == rt:
            return lt, []

        return self._new_aunifier(lt, rt)

    def antiunify(self, lt, rt) -> Tuple[Any, List[AunifyVar]]:
        if isinstance(lt, AunifyVar):
            if isinstance(rt, AunifyVar):
                lt.subs.extend(rt.subs)
            else:
                lt.subs.append(rt)
            return lt, [lt]

        if isinstance(rt, AunifyVar):
            rt.subs = [lt] + rt.subs
            return rt, [rt]

        if isinstance(lt, (list, tuple)):
            assert isinstance(rt, (list, tuple))
            return self._antiunify_lists(lt, rt)

        if not isinstance(lt, nodes.NodeNG) and not isinstance(rt, nodes.NodeNG):
            return self._aunify_consts(lt, rt)

        if not isinstance(lt, type(rt)):
            return self._new_aunifier(lt, rt, extra=f"{type(lt).__name__}-{type(rt).__name__}")

        # astroid.nodes of same type
        aunify_funcname = f"_aunify_{type(lt).__name__.lower()}"
        if hasattr(self, aunify_funcname):
            return getattr(self, aunify_funcname)(lt, rt)

        return self._aunify_by_attrs(lt, rt, [], lt._astroid_fields)

    def _antiunify_lists(
        self, lts: List[nodes.NodeNG], rts: List[nodes.NodeNG], attr: str = "<none>"
    ):
        if len(lts) != len(rts):
            attr_core, attr_avars = self._new_aunifier(
                lts,
                rts,
                extra=f"{attr}-{len(lts)}-{len(rts)}",
            )
            return [attr_core], attr_avars

        core = []
        avars = []
        for i in range(len(lts)):
            lt_child, rt_child = lts[i], rts[i]

            child_core, child_avars = self.antiunify(lt_child, rt_child)
            child_core = tuple(child_core) if isinstance(lt_child, tuple) else child_core

            core.append(child_core)
            avars.extend(child_avars)

        return core, avars

    def _aunify_many_attrs(self, attrs, lt, rt):
        avars = []
        attr_cores = {}

        for attr in attrs:
            assert hasattr(lt, attr), f"{type(lt).__name__} does not have '{attr}'"
            assert hasattr(rt, attr), f"{type(rt).__name__} does not have '{attr}'"

            lt_attr_val = getattr(lt, attr)
            rt_attr_val = getattr(rt, attr)

            attr_core, attr_avars = self.antiunify(lt_attr_val, rt_attr_val)
            attr_cores[attr] = attr_core

            avars.extend(attr_avars)

        return attr_cores, avars

    def _set_parents(self, core, node):
        if isinstance(node, nodes.NodeNG):
            node.parent = core
        elif isinstance(node, (list, tuple)):
            for elem in node:
                self._set_parents(core, elem)
        elif node is not None and not isinstance(node, (str, bool, int, float, bytes)):
            assert False, f"unreachable, but {type(node)}"

    def _aunify_by_attrs(self, lt, rt, attrs_before: List[str], attrs_after: List[str]):
        assert isinstance(
            lt, type(rt)
        ), f"lt type: {type(lt).__name__}, rt type: {type(rt).__name__}"

        attr_cores_before, avars_before = self._aunify_many_attrs(attrs_before, lt, rt)

        if isinstance(lt, (nodes.Arguments, nodes.Comprehension)):
            core = type(lt)()
        else:
            core = type(lt)(lineno=0, **attr_cores_before)

        # pylint overloads __getitem__ on nodes, so hasattr fails
        if not isinstance(lt, nodes.Const) and hasattr(lt, "cfg_loc"):
            assert hasattr(rt, "cfg_loc")
            core.cfg_loc = _to_list(lt.cfg_loc) + _to_list(rt.cfg_loc)

        for attr_core_before in attr_cores_before.values():
            self._set_parents(core, attr_core_before)

        attr_cores_after, avars_after = self._aunify_many_attrs(attrs_after, lt, rt)
        for attr, attr_core_after in attr_cores_after.items():
            setattr(core, attr, attr_core_after)
            self._set_parents(core, attr_core_after)

        return core, avars_before + avars_after

    def _aunify_by_attr(self, lt, rt, attr: str):
        return self._aunify_by_attrs(lt, rt, [], [attr])

    def _aunify_name(self, lt: nodes.Name, rt: nodes.Name):
        return self._aunify_by_attr(lt, rt, "name")

    def _aunify_assignname(self, lt: nodes.AssignName, rt: nodes.AssignName):
        return self._aunify_by_attr(lt, rt, "name")

    def _aunify_attribute(self, lt: nodes.Attribute, rt: nodes.Attribute):
        return self._aunify_by_attrs(lt, rt, [], ["expr", "attrname"])

    def _aunify_assignattr(self, lt: nodes.AssignAttr, rt: nodes.AssignAttr):
        return self._aunify_by_attrs(lt, rt, [], ["expr", "attrname"])

    def _aunify_boolop(self, lt: nodes.BoolOp, rt: nodes.BoolOp):
        return self._aunify_by_attrs(lt, rt, [], ["op", "values"])

    def _aunify_binop(self, lt: nodes.BinOp, rt: nodes.BinOp):
        return self._aunify_by_attrs(lt, rt, [], ["left", "op", "right"])

    def _aunify_unaryop(self, lt: nodes.UnaryOp, rt: nodes.UnaryOp):
        return self._aunify_by_attrs(lt, rt, [], ["op", "operand"])

    def _aunify_augassign(self, lt: nodes.AugAssign, rt: nodes.AugAssign):
        return self._aunify_by_attrs(lt, rt, [], ["target", "op", "value"])

    def _aunify_functiondef(self, lt: nodes.FunctionDef, rt: nodes.FunctionDef):
        return self._aunify_by_attrs(lt, rt, [], lt._astroid_fields + ("name",))

    def _aunify_const(self, lt: nodes.Const, rt: nodes.Const):
        return self._aunify_by_attrs(lt, rt, ["value"], [])

    def _aunify_nonlocal(self, lt: nodes.Nonlocal, rt: nodes.Nonlocal):
        return self._aunify_by_attrs(lt, rt, ["names"], [])

    def _aunify_global(self, lt: nodes.Global, rt: nodes.Global):
        return self._aunify_by_attrs(lt, rt, ["names"], [])

    def _aunify_importfrom(self, lt: nodes.ImportFrom, rt: nodes.ImportFrom):
        return self._aunify_by_attrs(lt, rt, ["modname", "names"], [])

    def _aunify_import(self, lt: nodes.Import, rt: nodes.Import):
        return self._aunify_by_attrs(lt, rt, [], ["modname", "names"])


def antiunify(lt: nodes.NodeNG, rt: nodes.NodeNG) -> Tuple[Any, List[AunifyVar]]:
    return Antiunify().antiunify(lt, rt)


##############################################################################
####                            to string                                 ####
##############################################################################


class AunifyVarAsString(nodes.as_string.AsStringVisitor):
    @staticmethod
    def from_aunifyvar(val):
        if isinstance(val, str):
            return val
        return val.name

    def visit_assign(self, node) -> str:
        """return an astroid.Assign node as string"""
        lhs = " = ".join(AunifyVarAsString.from_aunifyvar(n.accept(self)) for n in node.targets)
        return f"{lhs} = {node.value.accept(self)}"

    def visit_call(self, node) -> str:
        """return an astroid.Call node as string"""
        return super().visit_call(node)

    def visit_name(self, node) -> str:
        if isinstance(node.name, str):
            return node.name
        return node.name.name

    def visit_assignname(self, node) -> str:
        if isinstance(node.name, str):
            return node.name
        return node.name.name

    def _should_wrap(self, node, child, is_left: bool) -> bool:
        try:
            return super()._should_wrap(node, child, is_left)
        except KeyError:
            return True

    def visit_tuple(self, node) -> str:
        """return an astroid.Tuple node as string"""
        if len(node.elts) == 1:
            return f"({node.elts[0].accept(self)}, )"
        return f"({', '.join(child.accept(self) for child in node.elts)})"

    def visit_arguments(self, node) -> str:
        node_copy = copy.copy(node)
        node_copy.args = []
        for arg in node.args:
            if isinstance(arg, nodes.AssignName) and not isinstance(arg.name, str):
                arg_copy = copy.copy(arg)
                arg_copy.name = str(arg.name)
                node_copy.args.append(arg_copy)
            else:
                node_copy.args.append(arg)
        return node_copy.format_args()

    def visit_compare(self, node) -> str:
        """return an astroid.Compare node as string"""
        if not isinstance(node.ops, list):
            return f"{self._precedence_parens(node, node.left)} {node.ops}"

        rhs = []
        for pair in node.ops:
            if isinstance(pair, tuple):
                op, expr = pair
                rhs.append(f"{op} {self._precedence_parens(node, expr, is_left=False)}")
            else:
                rhs.append(pair.accept(self))
        return f"{self._precedence_parens(node, node.left)} {' '.join(rhs)}"

    def visit_dict(self, node) -> str:
        """return an astroid.Dict node as string"""
        return "{%s}" % ", ".join(self._visit_dict(node))

    def _visit_dict(self, node) -> Iterator[str]:
        for pair in node.items:
            if isinstance(pair, tuple):
                key, value = pair
                key = key.accept(self)
                value = value.accept(self)
                if key == "**":
                    # It can only be a DictUnpack node.
                    yield key + value
                else:
                    yield f"{key}: {value}"
            else:
                yield pair.name


def core_as_string(n) -> str:
    visitor = AunifyVarAsString()
    if isinstance(n, list):
        return "\n".join(n.accept(visitor) for n in n)
    return n.accept(visitor)


def eprint_aunify_core(n, depth: int = 0):
    def get_name(n):
        if isinstance(n, nodes.Const):
            return None
        if hasattr(n, "name"):
            return getattr(n, "name")
        if hasattr(n, "attrname"):
            return getattr(n, "attrname")
        return None

    if n is None:
        return

    eprint(depth * " ", type(n).__name__, sep="", end="")

    name = get_name(n)
    if name is not None:
        eprint(".", name, sep="", end="")
    eprint()

    for attr in n._astroid_fields:
        eprint((depth + 1) * " ", attr, sep="")
        children = getattr(n, attr)
        if not isinstance(children, list):
            children = [children]

        for child in children:
            if isinstance(child, tuple):
                op, child = child
                eprint((depth + 2) * " ", op)
            eprint_aunify_core(child, depth + 2)
