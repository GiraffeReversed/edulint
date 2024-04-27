from typing import Dict, Union, Tuple, List, Any, Iterator
import copy

from astroid import nodes

from edulint.linting.analyses.cfg.utils import syntactic_children_locs_from, get_cfg_loc
from edulint.linting.analyses.reaching_definitions import get_scope, get_vars_used_after
from edulint.linting.analyses.cfg.visitor import CFGVisitor
from edulint.linting.checkers.utils import eprint, cformat


subitution = Dict[str, Union[nodes.NodeNG, Tuple[str, nodes.NodeNG]]]


class AunifyVar(nodes.Name):
    def __init__(self, name: str):
        self.name = name.upper()
        self.parent = None
        self.lineno = 0
        self.subs = []
        self.sub_locs = []

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

    def __add__(self, other):
        return str(self) + other

    def __radd__(other, self):
        return other + str(self)

    def replace(self, old, new):
        return self.name.replace(old, new)


def _to_list(val):
    return val if isinstance(val, list) else [val]


class Antiunify:
    __num = 0

    def _get_new_avar(self, extra: str = None):
        self.__num += 1
        return AunifyVar(f"id_{self.__num}{('_' + extra) if extra is not None else ''}")

    def _new_aunifier(self, to_aunify: List[Any], extra: str = None):
        avar = self._get_new_avar(extra)
        avar.subs = to_aunify.copy()
        avar.sub_locs = [n.cfg_loc for n in to_aunify if hasattr(n, "cfg_loc")]
        return avar, [avar]

    def _aunify_consts(self, vals: List[Any]):
        if all(v == vals[0] for v in vals):
            return vals[0], []

        return self._new_aunifier(vals)

    def _aunify_avars(self, to_aunify: List[Any]):
        core = self._get_new_avar()

        for node in to_aunify:
            if isinstance(node, AunifyVar):
                core.subs.extend(node.subs)
                core.sub_locs.extend(node.sub_locs)
            else:
                core.subs.append(node)
                if hasattr(node, "cfg_loc"):
                    core.subs.append(node.cfg_loc)

        return core, [core]

    def antiunify(self, to_aunify: List[Any]) -> Tuple[Any, List[AunifyVar]]:
        if any(isinstance(n, AunifyVar) for n in to_aunify):
            return self._aunify_avars(to_aunify)

        if isinstance(to_aunify[0], (list, tuple)):
            assert all(isinstance(n, (list, tuple)) for n in to_aunify)
            return self._antiunify_lists(to_aunify)

        if not any(isinstance(n, nodes.NodeNG) for n in to_aunify):
            return self._aunify_consts(to_aunify)

        if not all(isinstance(n, type(to_aunify[0])) for n in to_aunify):
            return self._new_aunifier(
                to_aunify, extra="-".join(type(n).__name__ for n in to_aunify)
            )

        # astroid.nodes of same type
        aunify_funcname = f"_aunify_{type(to_aunify[0]).__name__.lower()}"
        if hasattr(self, aunify_funcname):
            return getattr(self, aunify_funcname)(to_aunify)

        return self._aunify_by_attrs(to_aunify, [], to_aunify[0]._astroid_fields)

    def _antiunify_lists(self, to_aunify: List[List[Any]], attr: str = "<none>"):
        if not all(len(n) == len(to_aunify[0]) for n in to_aunify):
            attr_core, attr_avars = self._new_aunifier(
                to_aunify,
                extra=f"{attr}-" + "-".join(str(len(n)) for n in to_aunify),
            )
            some = [v for n in to_aunify for v in n][0]
            if isinstance(some, tuple):
                fst, snd = some
                if isinstance(fst, str) and isinstance(snd, (str, type(None))):
                    return [(attr_core, None)], attr_avars
                elif isinstance(fst, str) and isinstance(snd, nodes.NodeNG):
                    return [("", attr_core)], attr_avars
            return [attr_core], attr_avars

        core = []
        avars = []
        for i in range(len(to_aunify[0])):
            children = [n[i] for n in to_aunify]

            child_core, child_avars = self.antiunify(children)
            child_core = tuple(child_core) if isinstance(children[0], tuple) else child_core

            core.append(child_core)
            avars.extend(child_avars)

        return core, avars

    def _aunify_many_attrs(self, attrs: List[str], to_aunify: List[Any]):
        avars = []
        attr_cores = {}

        for attr in attrs:
            attr_vals = [getattr(n, attr) for n in to_aunify]

            attr_core, attr_avars = self.antiunify(attr_vals)
            attr_cores[attr] = attr_core

            avars.extend(attr_avars)

        return attr_cores, avars

    def _set_parents(self, core: nodes.NodeNG, node: Any):
        if isinstance(node, nodes.NodeNG):
            node.parent = core
        elif isinstance(node, (list, tuple)):
            for elem in node:
                self._set_parents(core, elem)
        elif node is not None and not isinstance(node, (str, bool, int, float, bytes)):
            assert False, f"unreachable, but {type(node)}"

    def _aunify_by_attrs(self, to_aunify, attrs_before: List[str], attrs_after: List[str]):
        some = to_aunify[0]
        assert all(isinstance(n, type(some)) for n in to_aunify)

        attr_cores_before, avars_before = self._aunify_many_attrs(attrs_before, to_aunify)

        if isinstance(some, (nodes.Arguments, nodes.Comprehension)):
            core = type(some)()
        else:
            if isinstance(some, nodes.ImportFrom):
                attr_cores_before["fromname"] = attr_cores_before.pop("modname")
            core = type(some)(lineno=0, **attr_cores_before)

        # pylint overloads __getitem__ on constants, so hasattr would fail
        try:
            assert all(hasattr(n, "cfg_loc") or hasattr(n, "sub_locs") for n in to_aunify)
            core.sub_locs = [
                loc
                for node in to_aunify
                for loc in (
                    [getattr(node, "cfg_loc")]
                    if hasattr(node, "cfg_loc")
                    else getattr(node, "sub_locs")
                )
            ]
        except AssertionError:
            pass

        for attr_core_before in attr_cores_before.values():
            self._set_parents(core, attr_core_before)

        attr_cores_after, avars_after = self._aunify_many_attrs(attrs_after, to_aunify)
        for attr, attr_core_after in attr_cores_after.items():
            setattr(core, attr, attr_core_after)
            self._set_parents(core, attr_core_after)

        return core, avars_before + avars_after

    def _aunify_by_attr(self, to_aunify, attr: str):
        return self._aunify_by_attrs(to_aunify, [], [attr])

    def _aunify_name(self, to_aunify: List[nodes.Name]):
        return self._aunify_by_attr(to_aunify, "name")

    def _aunify_assignname(self, to_aunify: List[nodes.AssignName]):
        return self._aunify_by_attr(to_aunify, "name")

    def _aunify_attribute(self, to_aunify: List[nodes.Attribute]):
        return self._aunify_by_attrs(to_aunify, [], ["expr", "attrname"])

    def _aunify_assignattr(self, to_aunify: List[nodes.AssignAttr]):
        return self._aunify_by_attrs(to_aunify, [], ["expr", "attrname"])

    def _aunify_boolop(self, to_aunify: List[nodes.BoolOp]):
        return self._aunify_by_attrs(to_aunify, [], ["op", "values"])

    def _aunify_binop(self, to_aunify: List[nodes.BinOp]):
        return self._aunify_by_attrs(to_aunify, [], ["left", "op", "right"])

    def _aunify_unaryop(self, to_aunify: List[nodes.UnaryOp]):
        return self._aunify_by_attrs(to_aunify, [], ["op", "operand"])

    def _aunify_augassign(self, to_aunify: List[nodes.AugAssign]):
        return self._aunify_by_attrs(to_aunify, [], ["target", "op", "value"])

    def _aunify_functiondef(self, to_aunify: List[nodes.FunctionDef]):
        return self._aunify_by_attrs(to_aunify, [], to_aunify[0]._astroid_fields + ("name",))

    def _aunify_const(self, to_aunify: List[nodes.Const]):
        return self._aunify_by_attrs(to_aunify, ["value"], [])

    def _aunify_nonlocal(self, to_aunify: List[nodes.Nonlocal]):
        return self._aunify_by_attrs(to_aunify, ["names"], [])

    def _aunify_global(self, to_aunify: List[nodes.Global]):
        return self._aunify_by_attrs(to_aunify, ["names"], [])

    def _aunify_importfrom(self, to_aunify: List[nodes.ImportFrom]):
        return self._aunify_by_attrs(to_aunify, ["modname", "names"], [])

    def _aunify_import(self, to_aunify: List[nodes.Import]):
        return self._aunify_by_attrs(to_aunify, [], ["modname", "names"])


ASTROID_FIELDS = {
    nodes.Name: ["name"],
    nodes.AssignName: ["name"],
    nodes.Attribute: ["expr", "attrname"],
    nodes.AssignAttr: ["expr", "attrname"],
    nodes.BoolOp: ["op", "values"],
    nodes.BinOp: ["left", "op", "right"],
    nodes.UnaryOp: ["op", "operand"],
    nodes.AugAssign: ["target", "op", "value"],
    nodes.FunctionDef: ("name",) + nodes.FunctionDef._astroid_fields,
    nodes.Const: ["value"],
    nodes.Nonlocal: ["names"],
    nodes.Global: ["names"],
    nodes.ImportFrom: ["modname", "names"],
    nodes.Import: ["modname", "names"],
}


def get_avars(core: nodes.NodeNG, result: List[AunifyVar] = None) -> List[AunifyVar]:
    result = result if result is not None else []

    if isinstance(core, AunifyVar):
        result.append(core)

    elif isinstance(core, nodes.NodeNG):
        attrs = ASTROID_FIELDS.get(type(core), type(core)._astroid_fields)
        for attr in attrs:
            get_avars(getattr(core, attr), result)

    elif isinstance(core, (tuple, list)):
        for n in core:
            get_avars(n, result)

    return result


def can_be_removed(core, avar) -> bool:
    avar_loc = get_cfg_loc(avar)
    avar_sub_locs = avar_loc.node.sub_locs
    assert len(avar_sub_locs) == len(avar.subs)
    avar_scopes = [get_scope(sub, loc) for sub, loc in zip(avar.subs, avar_sub_locs)]

    to_remove = [avar]

    for core_loc in syntactic_children_locs_from(avar_loc, core):
        for i, loc in enumerate(core_loc.node.sub_locs):
            for loc_varname, loc_scope, _event in loc.var_events:
                if loc_varname == avar.subs[i] and loc_scope == avar_scopes[i]:
                    for loc_avar in get_avars(core_loc.node):
                        assert len(avar.subs) == len(loc_avar.subs)
                        if any(asub != lasub for asub, lasub in zip(avar.subs, loc_avar.subs)):
                            return False, to_remove
                        to_remove.append(loc_avar)
    return True, to_remove


def remove_renamed_identical_vars(core, avars: List[AunifyVar]):
    for avar in avars:
        vars_used_after = get_vars_used_after(core)
        if not isinstance(avar.parent, nodes.AssignName) or any(
            (sub, get_scope(sub, get_cfg_loc(avar).node.sub_locs[i])) in vars_used_after
            for i, sub in enumerate(avar.subs)
        ):
            continue

        remove, to_remove = can_be_removed(core, avar)
        if remove:
            for to_remove_avar in to_remove:
                if all(asub == trsub for asub, trsub in zip(avar.subs, to_remove_avar.subs)):
                    to_remove_avar.parent.name = avar.subs[0]

    return core, get_avars(core)


def antiunify(
    to_aunify: List[Union[nodes.NodeNG, List[nodes.NodeNG]]]
) -> Tuple[Any, List[AunifyVar]]:
    core, avars = Antiunify().antiunify(to_aunify)
    wrapper = nodes.Module("tmp")
    wrapper.id = "tmp"
    wrapper.body = core if isinstance(core, list) else [core]
    wrapper.accept(CFGVisitor())
    return remove_renamed_identical_vars(core, avars)


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

    def visit_importfrom(self, node) -> str:
        def _import_string(names) -> str:
            """return a list of (name, asname) formatted as a string"""
            _names = []
            for name, asname in names:
                if asname is not None:
                    _names.append(f"{name} as {asname}")
                else:
                    _names.append(name)
            return ", ".join(n if isinstance(n, str) else str(n) for n in _names)

        """return an astroid.ImportFrom node as string"""
        return "from {} import {}".format(
            "." * (node.level or 0) + node.modname, _import_string(node.names)
        )


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
