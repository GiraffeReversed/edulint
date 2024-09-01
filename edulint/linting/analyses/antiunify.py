from typing import Union, Tuple, List, Any, Iterator, Callable, Optional
import copy
from enum import Enum

from astroid import nodes

from edulint.linting.analyses.cfg.utils import syntactic_children_locs_from, get_cfg_loc
from edulint.linting.analyses.data_dependency import (
    Variable,
    get_vars_defined_before,
    get_vars_used_after,
    MODIFYING_EVENTS,
)
from edulint.linting.analyses.cfg.visitor import CFGVisitor
from edulint.linting.checkers.utils import new_node, eprint


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


class DisallowedAntiunification(Exception):
    pass


ASTROID_EXTRA_FIELDS = {
    nodes.Name: ("name",),
    nodes.AssignName: ("name",),
    nodes.Attribute: ("attrname",),
    nodes.AssignAttr: ("attrname",),
    nodes.BoolOp: ("op",),
    nodes.BinOp: ("op",),
    nodes.UnaryOp: ("op",),
    nodes.AugAssign: ("op",),
    nodes.FunctionDef: ("name",),
    nodes.Const: ("value",),
    nodes.Nonlocal: ("names",),
    nodes.Global: ("names",),
    nodes.ImportFrom: (
        "modname",
        "names",
    ),
    nodes.Import: ("names",),
    nodes.Keyword: ("arg",),
    nodes.Subscript: ("ctx",),
    nodes.Starred: ("ctx",),
    nodes.DelName: ("name",),
    nodes.DelAttr: ("attrname",),
}


def get_all_fields(node):
    return type(node)._astroid_fields + ASTROID_EXTRA_FIELDS.get(type(node), ())


class Antiunify:
    __num = 0

    def _get_new_avar(self, extra: str = None):
        self.__num += 1
        return AunifyVar(f"id_{self.__num}{('_' + extra) if extra is not None else ''}")

    def _new_aunifier(
        self, to_aunify: List[Any], stop_on: Callable[[List[AunifyVar]], bool], extra: str = None
    ):
        avar = self._get_new_avar(extra)
        avar.subs = to_aunify.copy()
        avar.sub_locs = [n.cfg_loc for n in to_aunify if hasattr(n, "cfg_loc")]

        if stop_on([avar]):
            raise DisallowedAntiunification()

        return avar, [avar]

    def _aunify_consts(self, vals: List[Any], stop_on: Callable[[List[AunifyVar]], bool]):
        if all(v == vals[0] for v in vals):
            return vals[0], []

        return self._new_aunifier(vals, stop_on)

    def _aunify_avars(self, to_aunify: List[Any], stop_on: Callable[[List[AunifyVar]], bool]):
        core = self._get_new_avar()

        for node in to_aunify:
            if isinstance(node, AunifyVar):
                core.subs.extend(node.subs)
                core.sub_locs.extend(node.sub_locs)
            else:
                core.subs.append(node)
                if hasattr(node, "cfg_loc"):
                    core.sub_locs.append(node.cfg_loc)

        if stop_on([core]):
            raise DisallowedAntiunification()

        return core, [core]

    def antiunify(
        self, to_aunify: List[Any], stop_on: Callable[[List[AunifyVar]], bool]
    ) -> Optional[Tuple[Any, List[AunifyVar]]]:
        if any(isinstance(n, AunifyVar) for n in to_aunify):
            return self._aunify_avars(to_aunify, stop_on)

        if isinstance(to_aunify[0], (list, tuple)):
            assert all(isinstance(n, (list, tuple)) for n in to_aunify)
            return self._antiunify_lists(to_aunify, stop_on)

        if not any(isinstance(n, nodes.NodeNG) for n in to_aunify):
            return self._aunify_consts(to_aunify, stop_on)

        if not all(isinstance(n, type(to_aunify[0])) for n in to_aunify):
            return self._new_aunifier(
                to_aunify, stop_on, extra="-".join(type(n).__name__ for n in to_aunify)
            )

        # astroid.nodes of same type
        some = to_aunify[0]
        all_fields = get_all_fields(some)

        return self._aunify_by_attrs(to_aunify, all_fields, stop_on)

    def _antiunify_lists(
        self,
        to_aunify: List[List[Any]],
        stop_on: Callable[[List[AunifyVar]], bool],
        attr: str = "<none>",
    ):
        if not all(len(n) == len(to_aunify[0]) for n in to_aunify):
            attr_core, attr_avars = self._new_aunifier(
                to_aunify,
                stop_on,
                extra=f"{attr}-" + "-".join(str(len(n)) for n in to_aunify),
            )
            some = [v for n in to_aunify for v in n][0]
            if isinstance(some, tuple):
                fst, snd = some
                if isinstance(fst, str) and isinstance(snd, (str, type(None))):
                    return [(attr_core, None)], attr_avars
                elif isinstance(fst, str) and isinstance(snd, nodes.NodeNG):
                    return [("", attr_core)], attr_avars
                elif isinstance(fst, nodes.NodeNG) and isinstance(snd, nodes.NodeNG):
                    other_core, _ = self._new_aunifier(
                        [], stop_on, extra=f"{attr}-" + "-".join(str(len(n)) for n in to_aunify)
                    )
                    return [(attr_core, other_core)], attr_avars
            return [attr_core], attr_avars

        core = []
        avars = []
        for i in range(len(to_aunify[0])):
            children = [n[i] for n in to_aunify]

            child_core, child_avars = self.antiunify(children, stop_on)
            child_core = tuple(child_core) if isinstance(children[0], tuple) else child_core

            core.append(child_core)
            avars.extend(child_avars)

        return core, avars

    def _aunify_many_attrs(
        self, attrs: List[str], to_aunify: List[Any], stop_on: Callable[[List[AunifyVar]], bool]
    ):
        avars = []
        attr_cores = {}

        for attr in attrs:
            attr_vals = [getattr(n, attr) for n in to_aunify]

            attr_core, attr_avars = self.antiunify(attr_vals, stop_on)
            attr_cores[attr] = attr_core

            avars.extend(attr_avars)

        return attr_cores, avars

    def _aunify_by_attrs(
        self,
        to_aunify,
        attrs: List[str],
        stop_on: Callable[[List[AunifyVar]], bool],
    ):
        some = to_aunify[0]
        assert all(isinstance(n, type(some)) for n in to_aunify)

        attr_cores, avars = self._aunify_many_attrs(attrs, to_aunify, stop_on)

        core = new_node(type(some), **attr_cores)

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

        for attr_core in attr_cores.values():
            set_parents(core, attr_core, recursive=False)

        if stop_on(avars):
            raise DisallowedAntiunification()

        return core, avars


def contains_avar(node: Union[nodes.NodeNG, List[nodes.NodeNG]], avars):
    if isinstance(node, nodes.NodeNG):
        ns = [node]
    elif not isinstance(node, (list, tuple)) or len(node) == 0:
        return False
    elif not isinstance(node[0], nodes.NodeNG):
        ns = [n for subn in node for n in subn]
    else:
        ns = node

    for avar in avars:
        for ancestor in avar.node_ancestors():
            if any(ancestor == n for n in ns):
                return True
    return False


def get_avars(core: nodes.NodeNG, result: List[AunifyVar] = None) -> List[AunifyVar]:
    result = result if result is not None else []

    if isinstance(core, AunifyVar):
        result.append(core)

    elif isinstance(core, nodes.NodeNG):
        all_fields = get_all_fields(core)
        for attr in all_fields:
            get_avars(getattr(core, attr), result)

    elif isinstance(core, (tuple, list)):
        for n in core:
            get_avars(n, result)

    return result


def ancestors_till(node: nodes.NodeNG, ancestor: nodes.NodeNG):
    result = []
    for parent in node.node_ancestors():
        if parent == ancestor:
            break
        result.append(parent)
    return result


def get_avar_parent_in_sub(avar_node, sub_node, avar):
    if avar_node == avar.parent:
        return sub_node

    if isinstance(avar_node, list):
        assert isinstance(sub_node, list) and len(avar_node) == len(sub_node)
        for an, sn in zip(avar_node, sub_node):
            if contains_avar(an, [avar]):
                return get_avar_parent_in_sub(an, sn, avar)
    else:
        for attr in get_all_fields(avar_node):
            avar_attr_node = getattr(avar_node, attr)
            if contains_avar(avar_attr_node, [avar]):
                return get_avar_parent_in_sub(avar_attr_node, getattr(sub_node, attr), avar)

    assert False, f"unreachable, but {avar}"


def sub_to_variable(avar, i):
    assert isinstance(avar.parent, nodes.AssignName)

    sub = avar.subs[i]
    avar_loc = get_cfg_loc(avar)
    sub_loc = avar_loc.node.sub_locs[i]

    event_nodes = list(
        {
            (var.scope, event.node)
            for var, event in sub_loc.var_events.for_name(sub)
            if event.type in MODIFYING_EVENTS
        }
    )
    if len(event_nodes) == 1:
        return Variable(sub, event_nodes[0][0])
    assert len(event_nodes) > 1

    sub_node = get_avar_parent_in_sub(avar_loc.node, sub_loc.node, avar)

    for scope, node in event_nodes:
        if node == sub_node:
            return Variable(sub, scope)

    assert False, f"unreachable, but {sub}"


def get_removable(core, avar) -> bool:
    assert isinstance(avar.parent, nodes.AssignName)
    avar_loc = get_cfg_loc(avar)

    to_remove = {avar}

    for ic, core_loc in enumerate(syntactic_children_locs_from(avar_loc, core)):
        if ic == 0:
            continue
        for il, loc in enumerate(core_loc.node.sub_locs):
            var = sub_to_variable(avar, il)
            if var in loc.var_events:
                for loc_avar in get_avars(core_loc.node):
                    assert len(avar.subs) == len(loc_avar.subs)
                    if any(asub != lasub for asub, lasub in zip(avar.subs, loc_avar.subs)):
                        return set()
                    to_remove.add(loc_avar)
    return to_remove


def remove_renamed_identical_vars(core, avars: List[AunifyVar]):
    if not any(isinstance(avar.parent, nodes.AssignName) for avar in avars):
        return core, avars

    vars_defined_before = get_vars_defined_before(core)
    vars_used_after = get_vars_used_after(core)
    irremovable_vars = set(vars_defined_before.keys()) | set(vars_used_after.keys())

    for avar in avars:
        if not isinstance(avar.parent, nodes.AssignName) or any(
            sub_to_variable(avar, i) in irremovable_vars for i, sub in enumerate(avar.subs)
        ):
            continue

        for to_remove_avar in get_removable(core, avar):
            to_remove_avar.parent.name = avar.subs[0]

    return core, get_avars(core)


def antiunify(
    to_aunify: List[Union[nodes.NodeNG, List[nodes.NodeNG]]],
    stop_on: Callable[[List[AunifyVar]], bool] = lambda _: False,
    stop_on_after_renamed_identical: Callable[[List[AunifyVar]], bool] = lambda _: False,
) -> Optional[Tuple[Any, List[AunifyVar]]]:
    try:
        core, avars = Antiunify().antiunify(to_aunify, stop_on)
    except DisallowedAntiunification:
        return None

    wrapper = new_node(nodes.Module, name="tmp", body=core if isinstance(core, list) else [core])
    wrapper.accept(CFGVisitor())

    core, avars = remove_renamed_identical_vars(core, avars)
    if stop_on_after_renamed_identical(avars):
        return None
    return core, avars


def set_parents(parent: nodes.NodeNG, node: Any, recursive):
    if isinstance(node, nodes.NodeNG):
        node.parent = parent

        if recursive:
            for attr in get_all_fields(node):
                children = getattr(node, attr)
                set_parents(node, children, recursive)

    elif isinstance(node, (list, tuple)):
        for elem in node:
            set_parents(parent, elem, recursive)

    elif node is not None and not isinstance(
        node, (str, bool, int, float, bytes, type(Ellipsis), Enum)
    ):
        assert False, f"unreachable, but {type(node)}"


def get_sub_variant(core, index: int):
    if isinstance(core, (list, tuple)):
        return type(core)([get_sub_variant(c, index) for c in core])

    if not isinstance(core, nodes.NodeNG):
        return core

    if isinstance(core, AunifyVar):
        variant = core.subs[index]

    else:
        attr_variants = {
            attr: get_sub_variant(getattr(core, attr), index) for attr in get_all_fields(core)
        }
        variant = new_node(type(core), **attr_variants)

        for attr, attr_variant in attr_variants.items():
            set_parents(variant, attr_variant, recursive=False)

    try:
        if len(core.sub_locs) > 0:
            variant.cfg_loc = core.sub_locs[index]
    except AttributeError:
        pass

    return variant


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


def cprint(n) -> None:
    eprint(core_as_string(n))


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
