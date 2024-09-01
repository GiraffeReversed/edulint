from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Union, Dict, Optional

from astroid import nodes


ScopeNode = Union[
    nodes.Module,
    nodes.FunctionDef,
    nodes.ClassDef,
    nodes.Lambda,
    nodes.GeneratorExp,
    nodes.ListComp,
    nodes.DictComp,
    nodes.SetComp,
]
VarName = str


@dataclass(frozen=True)
class Variable:
    name: VarName
    scope: ScopeNode


class VarEventType(Enum):
    ASSIGN = auto()
    REASSIGN = auto()
    MODIFY = auto()
    READ = auto()
    DELETE = auto()


@dataclass
class VarEvent:
    var: Variable
    node: nodes.NodeNG
    type: VarEventType
    definitions: List["VarEvent"] = field(default_factory=list)
    uses: List["VarEvent"] = field(default_factory=list)

    def __repr__(self) -> str:
        return (
            "VarEvent("
            f"node={self.node!r}, "
            f"var={self.var.name}, "
            f"type={self.type.name}, "
            f"len(definitions)={len(self.definitions)}, "
            f"len(uses)={len(self.uses)}"
            ")"
        )

    def is_direct_modify(self):
        """Method called on the var, e.g., append, insert"""
        assert self.type == VarEventType.MODIFY
        return isinstance(self.node.parent, nodes.Attribute) and isinstance(
            self.node.parent.parent, nodes.Call
        )


@dataclass
class VarEvents:
    var_events: Dict[Variable, List[VarEvent]] = field(default_factory=lambda: defaultdict(list))

    def all(self):
        for var, events in self.var_events.items():
            for event in events:
                yield var, event

    def for_var(self, var: Variable):
        return self.var_events[var]

    def for_name(self, varname: VarName):
        for var, events in self.var_events.items():
            if var.name == varname:
                for event in events:
                    yield var, event

    def add(self, var: Variable, event: VarEvent):
        self.var_events[var].append(event)

    def __iter__(self):
        return iter(self.var_events)

    def __contains__(self, needle) -> bool:
        return needle in self.var_events

    def __getattr__(self, attr: str):
        return getattr(self.var_events, attr)

    def __getitem__(self, key):
        return self.var_events[key]


def strip_to_name(
    node: nodes.NodeNG,
) -> Optional[Union[nodes.Name, nodes.AssignName, nodes.DelName]]:
    while True:
        if isinstance(node, nodes.Subscript):
            node = node.value
        elif type(node) in (nodes.Attribute, nodes.AssignAttr, nodes.DelAttr):
            node = node.expr
        else:
            break

    return node if isinstance(node, (nodes.Name, nodes.AssignName, nodes.DelName)) else None
