from typing import Dict, Union, Tuple, List, Any, Iterator
import copy

from astroid import nodes

from edulint.linting.checkers.utils import eprint


Substitution = Dict[str, Union[nodes.NodeNG, Tuple[str, nodes.NodeNG]]]


class AunifyVar(nodes.Name):
    def __init__(self, name: str):
        self.name = name.upper()
        self.parent = None
        self.lineno = 0

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


class Antiunify:
    __num = 0

    def _get_new_varname(self, extra: str = None):
        self.__num += 1
        return AunifyVar(f"id_{self.__num}{('_' + extra) if extra is not None else ''}")

    def _new_aunifier(self, lt: nodes.NodeNG, rt: nodes.NodeNG, extra: str = None):
        id_ = self._get_new_varname(extra)
        return id_, {id_: lt}, {id_: rt}

    def _aunify_consts(self, lt: Any, rt: Any):
        if lt == rt:
            return lt, {}, {}

        if isinstance(lt, AunifyVar):
            return lt, {}, {lt.name: rt}
        if isinstance(rt, AunifyVar):
            return rt, {rt.name: lt}, {}

        id_ = self._get_new_varname()
        return id_, {id_: lt}, {id_: rt}

    def antiunify_lists(
        self, lts: List[nodes.NodeNG], rts: List[nodes.NodeNG], attr: str = "<none>"
    ):
        if len(lts) != len(rts):
            attr_core, attr_lt_subst, attr_rt_subst = self._new_aunifier(
                lts,
                rts,
                extra=f"{attr}-{len(lts)}-{len(rts)}",
            )
            return [attr_core], attr_lt_subst, attr_rt_subst
        assert len(lts) == len(rts), lts[0].root().file

        core = []
        lt_subst = {}
        rt_subst = {}
        for i in range(len(lts)):
            lt_child, rt_child = lts[i], rts[i]
            assert isinstance(lt_child, tuple) == isinstance(
                rt_child, tuple
            ), f"lt type: {type(lt_child).__name__}, rt type: {type(rt_child).__name__}"

            if not isinstance(lt_child, tuple):
                child_core, child_lt_subst, child_rt_subst = self.antiunify(lt_child, rt_child)
                core.append(child_core)
                lt_subst.update(child_lt_subst)
                rt_subst.update(child_rt_subst)
            else:
                lt_fst, lt_snd = lt_child
                rt_fst, rt_snd = rt_child
                if (  # first is op, second is operand
                    isinstance(lt_fst, str)
                    and isinstance(lt_snd, nodes.NodeNG)
                    and isinstance(rt_fst, str)
                    and isinstance(rt_snd, nodes.NodeNG)
                ):
                    fst_core, fst_lt_subst, fst_rt_subst = self._aunify_consts(lt_fst, rt_fst)
                    snd_core, snd_lt_subst, snd_rt_subst = self.antiunify(lt_snd, rt_snd)
                elif all(
                    isinstance(n, nodes.NodeNG) or n is None
                    for n in (lt_fst, lt_snd, rt_fst, rt_snd)
                ):
                    fst_core, fst_lt_subst, fst_rt_subst = self.antiunify(lt_fst, rt_fst)
                    snd_core, snd_lt_subst, snd_rt_subst = self.antiunify(lt_snd, rt_snd)

                core.append((fst_core, snd_core))
                lt_subst.update(fst_lt_subst)
                lt_subst.update(snd_lt_subst)
                rt_subst.update(fst_rt_subst)
                rt_subst.update(snd_rt_subst)

        return core, lt_subst, rt_subst

    def antiunify(
        self, lt: nodes.NodeNG, rt: nodes.NodeNG
    ) -> Tuple[Any, Dict[str, nodes.NodeNG], Dict[str, nodes.NodeNG]]:
        if isinstance(lt, AunifyVar):
            return lt, {}, {lt.name: rt}

        if isinstance(rt, AunifyVar):
            return rt, {rt.name: lt}, {}

        if not isinstance(lt, type(rt)):
            return self._new_aunifier(lt, rt, extra=f"{type(lt).__name__}-{type(rt).__name__}")

        if lt is None:
            assert rt is None
            return None, {}, {}

        aunify_funcname = f"_aunify_{type(lt).__name__.lower()}"
        if hasattr(self, aunify_funcname):
            return getattr(self, aunify_funcname)(lt, rt)

        return self._aunify_by_attrs(lt._astroid_fields, lt, rt)

    def _set_parents(self, core, node):
        if isinstance(node, nodes.NodeNG):
            node.parent = core
        elif isinstance(node, list):
            for elem in node:
                if isinstance(elem, nodes.NodeNG):
                    elem.parent = core
                elif isinstance(elem, tuple):
                    for e in elem:
                        if isinstance(e, nodes.NodeNG):
                            e.parent = core
        elif node is not None and not isinstance(node, str):
            assert False, f"unreachable, but {type(node)}"

    def _aunify_by_attrs(self, attrs: List[str], lt, rt):
        assert isinstance(
            lt, type(rt)
        ), f"lt type: {type(lt).__name__}, rt type: {type(rt).__name__}"

        if isinstance(lt, (nodes.Arguments, nodes.Comprehension)):
            core = type(lt)()
        else:
            core = type(lt)(lineno=0)

        lt_subst = {}
        rt_subst = {}

        for attr in attrs:
            assert hasattr(lt, attr), f"{type(lt).__name__} does not have '{attr}'"
            assert hasattr(rt, attr), f"{type(rt).__name__} does not have '{attr}'"

            lt_attr_val = getattr(lt, attr)
            rt_attr_val = getattr(rt, attr)

            if isinstance(lt_attr_val, list):
                assert isinstance(rt_attr_val, list), f"rt type: {type(rt_attr_val).__name__}"
                attr_core, attr_lt_subst, attr_rt_subst = self.antiunify_lists(
                    lt_attr_val, rt_attr_val, attr=attr
                )
            elif isinstance(lt_attr_val, nodes.NodeNG):
                attr_core, attr_lt_subst, attr_rt_subst = self.antiunify(lt_attr_val, rt_attr_val)
            else:
                attr_core, attr_lt_subst, attr_rt_subst = self._aunify_consts(
                    lt_attr_val, rt_attr_val
                )

            setattr(core, attr, attr_core)
            self._set_parents(core, attr_core)

            lt_subst.update(attr_lt_subst)
            rt_subst.update(attr_rt_subst)

        return core, lt_subst, rt_subst

    def _aunify_by_attr(self, attr: str, lt, rt):
        return self._aunify_by_attrs([attr], lt, rt)

    def _aunify_name(self, lt: nodes.Name, rt: nodes.Name):
        return self._aunify_by_attr("name", lt, rt)

    def _aunify_assignname(self, lt: nodes.AssignName, rt: nodes.AssignName):
        return self._aunify_by_attr("name", lt, rt)

    def _aunify_attribute(self, lt: nodes.Attribute, rt: nodes.Attribute):
        return self._aunify_by_attrs(["expr", "attrname"], lt, rt)

    def _aunify_assignattr(self, lt: nodes.AssignAttr, rt: nodes.AssignAttr):
        return self._aunify_by_attrs(["expr", "attrname"], lt, rt)

    def _aunify_boolop(self, lt: nodes.BoolOp, rt: nodes.BoolOp):
        return self._aunify_by_attrs(["op", "values"], lt, rt)

    def _aunify_binop(self, lt: nodes.BinOp, rt: nodes.BinOp):
        return self._aunify_by_attrs(["left", "op", "right"], lt, rt)

    def _aunify_unaryop(self, lt: nodes.UnaryOp, rt: nodes.UnaryOp):
        return self._aunify_by_attrs(["op", "operand"], lt, rt)

    def _aunify_augassign(self, lt: nodes.AugAssign, rt: nodes.AugAssign):
        return self._aunify_by_attrs(["target", "op", "value"], lt, rt)

    def _aunify_functiondef(self, lt: nodes.FunctionDef, rt: nodes.FunctionDef):
        return self._aunify_by_attrs(lt._astroid_fields + ("name",), lt, rt)

    def _aunify_const(self, lt: nodes.Const, rt: nodes.Const):
        attr_core, attr_lt_subst, attr_rt_subst = self._aunify_consts(lt.value, rt.value)
        core = nodes.Const(attr_core)
        if isinstance(attr_core, AunifyVar):
            attr_core.parent = core
        return core, attr_lt_subst, attr_rt_subst

    def _aunify_strs(self, lt: str, rt: str):
        if lt != rt:
            return self._new_aunifier(lt, rt)
        return lt, {}, {}

    def _aunify_scope_modifier(
        self, lt: Union[nodes.Nonlocal, nodes.Global], rt: Union[nodes.Nonlocal, nodes.Global]
    ):
        if len(lt.names) != len(rt.names):
            names_core, names_lt_subst, names_rt_subst = self._new_aunifier(
                lt.names, rt.names, extra=f"names-{len(lt.names)}-{len(rt.names)}"
            )
            names_core = [names_core]
        else:
            names_core = []
            names_lt_subst = {}
            names_rt_subst = {}
            for lt_name, rt_name in zip(lt.names, rt.names):
                name, name_lt_subst, name_rt_subst = self._aunify_strs(lt_name, rt_name)
                names_core.append(name)
                names_lt_subst.update(name_lt_subst)
                names_rt_subst.update(name_rt_subst)
        core = type(lt)(names=names_core)
        self._set_parents(core, names_core)
        return core, names_lt_subst, names_rt_subst

    def _aunify_nonlocal(self, lt: nodes.Nonlocal, rt: nodes.Nonlocal):
        return self._aunify_scope_modifier(lt, rt)

    def _aunify_global(self, lt: nodes.Global, rt: nodes.Global):
        return self._aunify_scope_modifier(lt, rt)

    def _aunify_importfrom(self, lt: nodes.ImportFrom, rt: nodes.ImportFrom):
        modname_core, modname_lt_subst, modname_rt_subst = self._aunify_strs(lt.modname, rt.modname)
        if len(lt.names) != len(rt.names):
            names_core, names_lt_subst, names_rt_subst = self._new_aunifier(
                lt.names, rt.names, extra=f"names-{len(lt.names)}-{len(rt.names)}"
            )
            names_core = [names_core]
        else:
            names_core = []
            names_lt_subst = {}
            names_rt_subst = {}
            for (lt_name, lt_alias), (rt_name, rt_alias) in zip(lt.names, rt.names):
                name, name_lt_subst, name_rt_subst = self._aunify_strs(lt_name, rt_name)
                alias, alias_lt_subst, alias_rt_subst = self._aunify_strs(lt_alias, rt_alias)
                names_core.append((name, alias))
                names_lt_subst.update(name_lt_subst)
                names_lt_subst.update(alias_lt_subst)
                names_rt_subst.update(name_rt_subst)
                names_rt_subst.update(alias_rt_subst)

        core = type(lt)(fromname=modname_core, names=names_core)
        self._set_parents(core, modname_core)
        self._set_parents(core, names_core)
        return (
            core,
            {**modname_lt_subst, **names_lt_subst},
            {**modname_rt_subst, **names_rt_subst},
        )


def antiunify(
    lt: nodes.NodeNG, rt: nodes.NodeNG
) -> Tuple[Any, Dict[str, nodes.NodeNG], Dict[str, nodes.NodeNG]]:
    return Antiunify().antiunify(lt, rt)


def antiunify_lists(
    lts: List[nodes.NodeNG], rts: List[nodes.NodeNG]
) -> Tuple[Any, Dict[str, nodes.NodeNG], Dict[str, nodes.NodeNG]]:
    return Antiunify().antiunify_lists(lts, rts)


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
