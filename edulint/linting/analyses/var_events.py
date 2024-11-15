from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Union, Dict, Optional, Iterator, Tuple

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
    """Class for storing information on an event that happened to a variable at a given place in code.

    Attributes:
        var (Variable): The variable the event relates to.
        node (nodes.NodeNG): Usually a nodes.Name or nodes.AssignName of the variable in the AST.
        type (VarEventType): The type of event happening here.
        definitions (Optional[List[VarEvent]]): For READ and MODIFY, this list gives events when the
          variable was last modified.
        uses (Optional[List[VarEvent]]): For ASSIGN, REASSIGN, MODIFY, this list gives events when the
          variable is being used.
    """

    var: Variable
    node: nodes.NodeNG
    type: VarEventType
    definitions: Optional[List["VarEvent"]] = field(default_factory=list)
    uses: Optional[List["VarEvent"]] = field(default_factory=list)
    redefines: Optional[List["VarEvent"]] = field(default_factory=list)
    redefined_by: Optional[List["VarEvent"]] = field(default_factory=list)

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
        """Checks if method is called on the var, e.g., append, insert"""
        assert self.type == VarEventType.MODIFY
        return isinstance(self.node.parent, nodes.Attribute) and isinstance(
            self.node.parent.parent, nodes.Call
        )


@dataclass
class VarEvents:
    """Class for storing information on events that are happening to variables in a given CFG location.
    Behaves as a dictionary, when methods are called on it.

    Attributes:
        var_events (Dict[Variable, List[VarEvents]]): For each variable, stores events happening to the
          variable in this location.
    """

    var_events: Dict[Variable, List[VarEvent]] = field(default_factory=lambda: defaultdict(list))

    def all(self) -> Iterator[Tuple[Variable, VarEvent]]:
        """Helper method for iterating over all events."""
        for var, events in self.var_events.items():
            for event in events:
                yield var, event

    def for_var(self, var: Variable) -> Iterator[VarEvent]:
        """Helper method for iterating over events for a variable."""
        return self.var_events[var]

    def for_name(self, varname: VarName) -> Iterator[Tuple[Variable, VarEvent]]:
        """Helper method for iterating over events for a variable name."""
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


def unstrip(
    node: Union[nodes.Name, nodes.AssignName, nodes.DelName],
) -> Union[
    nodes.Name,
    nodes.AssignName,
    nodes.DelName,
    nodes.Subscript,
    nodes.Attribute,
    nodes.AssignAttr,
    nodes.DelAttr,
]:
    while isinstance(
        node.parent, (nodes.Subscript, nodes.Attribute, nodes.AssignAttr, nodes.DelAttr)
    ):
        node = node.parent
    return node
