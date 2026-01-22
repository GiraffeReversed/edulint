from typing import List, Union, Set, Optional, Dict, Tuple, Iterator
from collections import defaultdict
from functools import lru_cache
from queue import deque

from astroid import nodes

from edulint.linting.analyses.cfg.graph import CFGLoc, CFGBlock
from edulint.linting.analyses.cfg.utils import (
    successor_blocks_from_locs,
    predecessors_from_loc,
    syntactic_children_locs,
    syntactic_children_locs_from,
    get_cfg_loc,
)
from edulint.linting.analyses.var_events import (
    VarEventType,
    Variable,
    VarName,
    VarEvent,
    strip_to_name,
    ScopeNode,
)
from edulint.linting.analyses.utils import is_builtin, node_to_event


MODIFYING_EVENTS = (VarEventType.ASSIGN, VarEventType.REASSIGN, VarEventType.MODIFY)
KILLING_EVENTS = (
    VarEventType.ASSIGN,
    VarEventType.REASSIGN,
    VarEventType.DELETE,
    VarEventType.MODIFY,
)
GENERATING_EVENTS = (VarEventType.READ, VarEventType.MODIFY)
# # MODIFYING_EVENTS = (VarEventType.ASSIGN, VarEventType.REASSIGN, VarEventType.SURE_MODIFY)
# KILLING_EVENTS = (VarEventType.ASSIGN, VarEventType.DELETE)
# GENERATING_EVENTS = (VarEventType.READ,)


### collectors


def get_calls(node: nodes.NodeNG, toplevel=True) -> Iterator[nodes.Call]:
    if not toplevel or isinstance(
        node, (nodes.Expr, nodes.Assign, nodes.AugAssign, nodes.AnnAssign)
    ):
        if isinstance(node, nodes.Call):
            yield node
        for child in node.get_children():
            yield from get_calls(child, toplevel=False)


def has_just_recursive_calls(graph, node):
    """
    graph: dict[node, set[node]]
    A: node
    returns True if there exists B such that B ->* A but A -/>* B
    """

    def reachable_from(start, g):
        visited = set()
        stack = list(g.get(start, []))
        while stack:
            u = stack.pop()
            if u in visited:
                continue
            visited.add(u)
            stack.extend(g.get(u, []))
        return visited

    # Nodes reachable from A
    from_node = reachable_from(node, graph)

    # Build reverse graph
    reverse_graph = defaultdict(set)
    for u, neighbors in graph.items():
        for v in neighbors:
            reverse_graph[v].add(u)

    # Nodes that can reach A
    to_node = reachable_from(node, reverse_graph)

    return from_node == to_node


def get_uncalled_functions(function_defs, call_graph):
    return set(function_defs) - {
        callee
        for caller, callees in call_graph.items()
        if isinstance(caller, nodes.FunctionDef)
        and not has_just_recursive_calls(call_graph, caller)
        for callee in callees
        if isinstance(callee, nodes.FunctionDef)
    }


def collect_gens_kill(
    block: CFGBlock,
) -> Tuple[Dict[Variable, List[VarEvent]], Dict[Variable, List[VarEvent]]]:
    gens, kill = defaultdict(list), defaultdict(list)
    for loc in block.locs:
        for var, event in loc.var_events.all():
            if event.type in GENERATING_EVENTS:
                if var not in kill:
                    gens[var].append(event)
                else:
                    kill_event = kill[var][-1]

                    if kill_event not in event.definitions:
                        event.definitions.append(kill_event)
                        kill_event.uses.append(event)

            if event.type in KILLING_EVENTS:
                if var in kill:
                    kill_event = kill[var][-1]
                    if kill_event not in event.redefines:
                        event.redefines.append(kill_event)
                        kill_event.redefined_by.append(event)
                kill[var].append(event)

    return gens, kill


@lru_cache(maxsize=128)
def ones_indices(n):
    result = []
    for i in range(n.bit_length()):
        if (n >> i) & 1:
            result.append(i)
    return result


def collect_reaching_definitions(  # blocks fun gen kills
    node: nodes.Module,
    variables: List[Variable],
    function_defs: List[nodes.FunctionDef],
    call_graph: Dict[ScopeNode, Set[ScopeNode]],
    outside_scope_events: Dict[ScopeNode, List[VarEvent]],
    nope,
) -> int:

    def get_fun_to_process(function_defs, call_graph, processed) -> Optional[nodes.FunctionDef]:
        unprocssed_defs = [fun_def for fun_def in function_defs if fun_def not in processed]
        if len(unprocssed_defs) == 0:
            return None

        fun_unprocessed_callees = {
            fun_def: call_graph[fun_def] - processed for fun_def in unprocssed_defs
        }
        sorted_fun_unprocessed_callees = sorted(
            fun_unprocessed_callees.items(), key=lambda fd_callees: len(fd_callees[1])
        )
        return sorted_fun_unprocessed_callees[0][0]

    def collect_events_in_called(graph, node_values, start):
        """
        graph: dict[node, set[node]]
        node_values: dict[node, iterable]
        start: node to start traversal from
        """
        visited = set()
        collected = []

        def dfs(node):
            if node in visited:
                return
            visited.add(node)

            # Collect this node's values
            collected.extend(node_values.get(node, []))

            # Visit neighbors
            for neighbor in graph.get(node, []):
                dfs(neighbor)

        dfs(start)
        return collected

    def collect_original_kills(
        var_to_index: Dict[Variable, int],
        index_to_block: List[CFGBlock],
        original_gens_kills,
        outside_scope_events,
        unresolved_calls,
        start_loc: CFGLoc,
    ):
        blocks = {}
        for block, _from, _to in successor_blocks_from_locs([start_loc], include_start=True):
            blocks[block] = len(blocks)
            index_to_block.append(block)
            gens, kill = defaultdict(list), defaultdict(list)
            for loc in block.locs:
                for call in get_calls(loc.node):
                    if isinstance(call.func, nodes.Name):
                        possible_callees = [
                            callee
                            for var, event in get_cfg_loc(call).var_events.for_node(call.func)
                            for callee in call_graph[event.node.scope()]
                            if isinstance(callee, nodes.FunctionDef) and callee.name == var.name
                        ]
                        if is_builtin(call.func):
                            continue
                    else:
                        possible_callees = []

                    if len(possible_callees) == 0:
                        unresolved_calls.append(call)
                        possible_callees = function_defs

                    for called_fun in possible_callees:
                        for in_call_event in collect_events_in_called(
                            call_graph, outside_scope_events, called_fun
                        ):
                            if (
                                in_call_event.node.parent == call
                                and in_call_event.node.parent.func == in_call_event.node
                            ):
                                continue

                            in_call_var_i = var_to_index[in_call_event.var]
                            if in_call_event.type in GENERATING_EVENTS:
                                if len(kill[in_call_var_i]) == 0:
                                    gens[in_call_var_i].append(in_call_event)
                                else:
                                    for kill_event in kill[in_call_var_i][-1]:
                                        if kill_event not in in_call_event.definitions:
                                            in_call_event.definitions.append(kill_event)
                                            kill_event.uses.append(in_call_event)
                            if in_call_event.type in KILLING_EVENTS:
                                if len(kill[in_call_var_i]) > 0:
                                    # TODO fix
                                    for kill_event in kill[in_call_var_i][-1]:
                                        if kill_event not in in_call_event.redefines:
                                            in_call_event.redefines.append(kill_event)
                                            kill_event.redefined_by.append(in_call_event)
                                else:
                                    kill[in_call_var_i].append([])
                                kill[in_call_var_i][-1].append(in_call_event)

                for var, event in loc.var_events.all():
                    var_i = var_to_index[var]
                    if event.type in GENERATING_EVENTS:
                        if len(kill[var_i]) == 0:
                            gens[var_i].append(event)
                        else:
                            for kill_event in kill[var_i][-1]:
                                if kill_event not in event.definitions:
                                    event.definitions.append(kill_event)
                                    kill_event.uses.append(event)

                    if event.type in KILLING_EVENTS:
                        if len(kill[var_i]) > 0:
                            for kill_event in kill[var_i][-1]:
                                if kill_event not in event.redefines:
                                    event.redefines.append(kill_event)
                                    kill_event.redefined_by.append(event)
                        kill[var_i].append([event])

            original_gens_kills.append((gens, kill))

        return blocks

    def collect_computed_kills(original_gens_kills, computed_kills, blocks, init_occupied_blocks):
        for block_i in range(len(blocks)):
            _gens, kills = original_gens_kills[init_occupied_blocks + block_i]
            computed_kills.append(
                # defaultdict(
                #     PlaceholderVarVal,
                #     {
                #         var_i: PlaceholderVarVal(1 << (init_occupied_blocks + block_i))
                #         for var_i, events in kills.items()
                #         if len(events) > 0
                #     },
                # )
                defaultdict(
                    int,
                    {
                        var_i: 1 << (init_occupied_blocks + block_i)
                        for var_i, events in kills.items()
                        if len(events) > 0
                    },
                )
            )

    def collect_kills_from_parents(computed_kills, all_parent_kills, blocks, init_occupied_blocks):
        for block in blocks:
            if len(block.predecessors) == 0:
                all_parent_kills.append(
                    # {var_i: PlaceholderVarVal(0, replace=True) for var_i in var_to_index.values()}
                    defaultdict(int)
                )
                continue

            # result = defaultdict(PlaceholderVarVal)
            result = defaultdict(int)
            for edge in block.predecessors:
                parent = edge.source
                if not parent.reachable:
                    continue

                for var_i, val in computed_kills[init_occupied_blocks + blocks[parent]].items():
                    result[var_i] |= val

            all_parent_kills.append(result)

    def fixpoint(
        original_gens_kills, computed_kills, all_parent_kills, blocks, init_occupied_blocks
    ):
        to_process = deque(enumerate(blocks.keys()))
        while to_process:
            i, block = to_process.popleft()
            parent_kills = all_parent_kills[init_occupied_blocks + i]
            _gens, original_kill = original_gens_kills[init_occupied_blocks + i]
            computed_kill = computed_kills[init_occupied_blocks + i]

            updated = []
            for var_i, val in parent_kills.items():
                if computed_kill[var_i] != val and len(original_kill[var_i]) == 0:
                    computed_kill[var_i] = val
                    updated.append((var_i, val))

            for edge in block.successors:
                if len(edge.target.locs) == 0:
                    continue
                j = blocks[edge.target]
                child_kills = all_parent_kills[init_occupied_blocks + j]
                for var_i, val in updated:
                    if val & child_kills[var_i] != val:
                        child_kills[var_i] |= val
                        if (j, edge.target) not in to_process:
                            to_process.append((j, edge.target))

    def connect_events(index_to_block, all_parent_kills, original_gens_kills):
        for block_i in range(len(index_to_block)):
            parent_kills = all_parent_kills[block_i]
            gens, original_kill = original_gens_kills[block_i]

            for var_i, val in parent_kills.items():
                if len(gens[var_i]) == 0 and len(original_kill[var_i]) == 0:
                    continue

                for index in ones_indices(val):
                    for kill_event in original_gens_kills[index][1][var_i][-1]:

                        if len(original_kill[var_i]) > 0:
                            for other_kill_event in original_kill[var_i][0]:
                                kill_event.redefined_by.append(other_kill_event)
                                other_kill_event.redefines.append(kill_event)

                        for gen_event in gens[var_i]:
                            gen_event.definitions.append(kill_event)
                            kill_event.uses.append(gen_event)

    def make_up_calls(blocks, computed_kills, original_gens_kills, init_occupied_blocks):
        uncalled_functions = get_uncalled_functions(function_defs, call_graph)
        if len(uncalled_functions) == 0:
            return

        module_kills = defaultdict(list)
        for block, block_i in blocks.items():
            if any(len(edge.target.locs) == 0 for edge in block.successors):
                for var_i, val in computed_kills[init_occupied_blocks + block_i].items():
                    for index in ones_indices(val):
                        for kill_event in original_gens_kills[index][1][var_i][-1]:
                            module_kills[var_i].append(kill_event)

        gens = []
        kills = []
        # TODO use collect_events_in_called(call_graph, outside_scope_events, uncalled_fun)
        for uncalled_fun in uncalled_functions:
            gens.append(defaultdict(list))
            kills.append(defaultdict(list))
            block_i = index_to_block.index(uncalled_fun.args.cfg_loc.block)
            while (
                block_i < len(index_to_block)
                and index_to_block[block_i].locs[0].node.scope() == uncalled_fun
            ):
                original_gens, original_kills = original_gens_kills[block_i]

                for var_i, gen_events in original_gens.items():
                    var_scope = variables[var_i].scope
                    if var_scope != uncalled_fun and scope_is_nested(
                        uncalled_fun, uncalled_fun.root()
                    ):
                        gens[-1][var_i].extend(gen_events)

                for var_i, kill_events in original_kills.items():
                    var_scope = variables[var_i].scope
                    if (
                        len(kill_events) > 0
                        and var_scope != uncalled_fun
                        and scope_is_nested(uncalled_fun, uncalled_fun.root())
                    ):
                        kills[-1][var_i].extend(kill_events[0])

                block_i += 1

        for kill in [module_kills] + kills:
            for var_i, kill_events in kill.items():
                for kill_event in kill_events:
                    for gen in gens:
                        for gen_event in gen[var_i]:
                            if kill_event not in gen_event.definitions:
                                gen_event.definitions.append(kill_event)
                                kill_event.uses.append(gen_event)

                    for other_kill in kills:
                        for other_kill_event in other_kill[var_i]:
                            if kill_event not in other_kill_event.redefines:
                                other_kill_event.redefines.append(kill_event)
                                kill_event.redefined_by.append(other_kill_event)

    if len(node.body) == 0:
        return

    var_to_index = {var: var_i for var_i, var in enumerate(variables)}
    index_to_block = []
    original_gens_kills = []
    computed_kills = []
    all_parent_kills = []
    unresolved_calls = []

    for loc in [fun_def.args.cfg_loc for fun_def in function_defs] + [node.body[0].cfg_loc]:
        init_occupied_blocks = len(index_to_block)
        blocks = collect_original_kills(
            var_to_index,
            index_to_block,
            original_gens_kills,
            outside_scope_events,
            unresolved_calls,
            loc,
        )
        collect_computed_kills(original_gens_kills, computed_kills, blocks, init_occupied_blocks)
        collect_kills_from_parents(computed_kills, all_parent_kills, blocks, init_occupied_blocks)
        fixpoint(
            original_gens_kills, computed_kills, all_parent_kills, blocks, init_occupied_blocks
        )
    connect_events(index_to_block, all_parent_kills, original_gens_kills)
    # DANGER call relies on node.body[0].cfg_loc being the last processed
    make_up_calls(blocks, computed_kills, original_gens_kills, init_occupied_blocks)
    node.function_defs = function_defs
    node.call_graph = call_graph
    node.unresolved_calls = unresolved_calls

    node.block_kills = {
        index_to_block[block_i]: {
            # variables[var_i]: [index_to_block[block_i] for block_i in ones_indices(val)]
            variables[var_i]: [
                event
                for block_i in ones_indices(val)
                for event in original_gens_kills[block_i][1][var_i][-1]
            ]
            for var_i, val in vars_events.items()
            if val > 0
        }
        for block_i, vars_events in enumerate(computed_kills)
    }


### var getters


def vars_in(
    node: Union[nodes.NodeNG, List[nodes.NodeNG]], event_types: Optional[Set[VarEventType]] = None
) -> Dict[Variable, List[nodes.NodeNG]]:
    """
    Returns variables and nodes associated with each, that appear in a node or a code block.

    Args:
        node (Union[nodes.NodeNG, List[nodes.NodeNG]]): Node or nodes to search in.
        event_types (Optional[Set[VarEventTypes]]): Report only selected events. If set to None
          (default), reports all event types.
    """
    result = {}

    if isinstance(node, nodes.NodeNG):
        loc_node = get_cfg_loc(node).node
    else:
        loc_node = node

    for loc in syntactic_children_locs(loc_node):
        for var, event in loc.var_events.all():
            if event_types is None or event.type in event_types:
                if loc_node == node or (event.node == node or node in event.node.node_ancestors()):
                    result.setdefault(var, []).append(event.node)
    return result


def name_to_var(name: str, node: nodes.NodeNG) -> Optional[Variable]:
    """Returns variable with given name inside the given node, which also determines the variables scope."""
    start = get_cfg_loc(node)
    for loc in syntactic_children_locs_from(start, node):
        for var, events in loc.var_events.items():
            event_scope = events[0].node.scope()
            if var.name == name and event_scope == node.scope():
                return var
    return None


def _get_matching_superpart(var_node: nodes.NodeNG, super_node: nodes.NodeNG):
    stripped = strip_to_name(super_node)
    while stripped != super_node:
        stripped = stripped.parent
        var_node = var_node.parent

        if not isinstance(var_node, type(stripped)):
            return None

        if isinstance(stripped, (nodes.Attribute, nodes.AssignAttr, nodes.DelAttr)):
            if stripped.attrname != var_node.attrname:
                return None

        elif isinstance(stripped, nodes.Subscript):
            stripped_vars = set(vars_in(stripped.slice).keys())
            node_vars = set(vars_in(var_node.slice).keys())
            stripped_events = get_events_by_var(stripped_vars, [stripped.slice])
            node_events = get_events_by_var(node_vars, [var_node.slice])
            if list(stripped_events.keys()) != list(node_events.keys()):
                return None

            for var in stripped_events.keys():
                if [e.definitions for e in stripped_events[var]] != [
                    e.definitions for e in node_events[var]
                ]:
                    return None
        else:
            assert False, "unreachable, but " + str(type(stripped))
    return var_node


def filter_events_for(
    node: Union[nodes.Name, nodes.AssignName, nodes.Attribute], events: List[VarEvent]
) -> List[VarEvent]:
    """
    Filter events that happen directly to the given node, not to its part (e.g. through
    a subscript or attribute).
    """
    if isinstance(node, (nodes.Name, nodes.AssignName)):
        return events

    result = []
    for event in events:
        superpart = _get_matching_superpart(event.node, node)
        if superpart is not None:
            result.append(VarEvent(event.var, superpart, event.type, None, None, None, None))
    return result


### iterators

_ASSIGNING_EXPRESSIONS = (nodes.Assign, nodes.AnnAssign, nodes.AugAssign, nodes.NamedExpr)
_ASSIGNING_ITERS = (nodes.For, nodes.Comprehension)
_ASSIGNING_STATEMENTS = (nodes.Import, nodes.ImportFrom, nodes.FunctionDef, nodes.ClassDef)
_ASSIGNING_PARENT_STATEMENTS = (nodes.Arguments, nodes.With, nodes.ExceptHandler, nodes.MatchAs)


def get_assigned_expressions(
    node: nodes.Name, include_nodes: List[type], include_destructuring: bool
) -> Iterator[nodes.NodeNG]:
    """
    Iterates over expressions that are assigned to a variable identified by given node.

    Args:
        node (nodes.Name): the node identifying the variable
        include_nodes (List[type]): types of irregular nodes to be included (e.g. FunctionDef, Arguments, For, With,
          ExceptHandler, which can also assign to a variable, but not a specific expression)
        include_destructuring (bool): whether to include expressions which are destructured before assigning to the
          variable (e.g. whether should return `divmod(x, y)` for assignment `div, mod = divmod(x, y)` when
          collecting expressions assigned to `div`, or `range(10)` when assigning to `i` in `for i in range(10)`).
    """
    event = node_to_event(node)
    if event is None:
        return

    for def_event in event.definitions:
        if def_event.type not in (VarEventType.ASSIGN, VarEventType.REASSIGN):
            continue
        if isinstance(def_event.node, _ASSIGNING_STATEMENTS):
            if type(def_event.node in include_nodes):
                yield def_event.node
            continue
        assert isinstance(def_event.node, nodes.AssignName)

        parent = def_event.node.parent
        if isinstance(parent, nodes.FunctionDef) and (
            def_event.node == parent.args.vararg_node or def_event.node == parent.args.kwarg_node
        ):
            parent = parent.args

        if isinstance(parent, _ASSIGNING_EXPRESSIONS):
            if parent.value is not None:  # AnnAssign-style declaration
                yield parent.value
        elif isinstance(parent, _ASSIGNING_ITERS):
            if include_destructuring:
                yield parent.iter
        elif isinstance(parent, _ASSIGNING_PARENT_STATEMENTS):
            if type(parent) in include_nodes:
                yield parent
        else:

            parents = [def_event.node]
            while not isinstance(parent, _ASSIGNING_EXPRESSIONS + _ASSIGNING_ITERS):
                parents.append(parent)
                parent = parent.parent
            assigning = parent

            if isinstance(assigning, _ASSIGNING_ITERS):
                if include_destructuring:
                    yield assigning.iter
            else:
                expr = assigning.value

                require_destructuring = False
                for child in reversed(parents):
                    if (
                        not isinstance(child.parent, nodes.Tuple)
                        or not isinstance(expr, nodes.Tuple)
                        or len(child.parent.elts) != len(expr.elts)
                    ):
                        require_destructuring = True
                        break

                    i = child.parent.elts.index(child)
                    expr = expr.elts[i]
                if not require_destructuring or include_destructuring:
                    yield expr


### event checkers


def is_changed_between(var: Variable, before_loc: CFGLoc, after_locs: List[CFGLoc]) -> bool:
    for after_loc in after_locs:
        for loc in predecessors_from_loc(
            after_loc, stop_on_loc=lambda loc: loc == before_loc, include_start=True
        ):
            for event in loc.var_events[var]:
                if event.type != VarEventType.READ:
                    return True
    return False


def get_events_in(
    nodes: List[nodes.NodeNG], event_types: Optional[List[VarEventType]] = None
) -> Iterator[VarEvent]:
    if len(nodes) == 0:
        return

    loc_nodes = [get_cfg_loc(n).node for n in nodes]
    check_ancestors = all(n == ln for n, ln in zip(nodes, loc_nodes))
    for loc in syntactic_children_locs(loc_nodes, explore_functions=False, explore_classes=False):
        for _var, event in loc.var_events.all():
            if (event_types is None or event.type in event_types) and (
                not check_ancestors
                or any(event.node == n or n in event.node.node_ancestors() for n in nodes)
            ):
                yield event


def get_events_for(
    vars: List[Variable],
    nodes: List[nodes.NodeNG],
    event_types: Optional[List[VarEventType]] = None,
) -> Iterator[VarEvent]:
    """
    Iterates over events for given variables in given code block.

    Args:
        vars (List[Variable]): variables to collect events for
        nodes (List[nodes.NodeNG]): list of nodes to collect in (including syntactic children)
        event_types (Optional[List[VarEventTypes]]): collect only selected event types; default
          (None) means collecting all.
    """
    if len(nodes) == 0:
        return

    loc_nodes = [get_cfg_loc(n).node for n in nodes]
    check_ancestors = all(n == ln for n, ln in zip(nodes, loc_nodes))
    for loc in syntactic_children_locs(loc_nodes, explore_functions=True, explore_classes=True):
        for var in vars:
            for event in loc.var_events.for_var(var):
                if (event_types is None or event.type in event_types) and (
                    not check_ancestors
                    or any(event.node == n or n in event.node.node_ancestors() for n in nodes)
                ):
                    yield event


def get_events_by_var(
    vars: List[Variable],
    nodes: List[nodes.NodeNG],
    event_types: Optional[List[VarEventType]] = None,
) -> Dict[Variable, List[VarEvent]]:
    """
    Returns a dictionary, mapping variables to events for given variables in given code block.

    Args:
        vars (List[Variable]): variables to collect events for
        nodes (List[nodes.NodeNG]): list of nodes to collect in (including syntactic children)
        event_types (Optional[List[VarEventTypes]]): collect only selected event types; default
          (None) means collecting all.
    """
    result = defaultdict(list)
    for event in get_events_for(vars, nodes, event_types):
        result[event.var].append(event)
    return result


def get_defs_at(node: nodes.NodeNG, varname: VarName) -> List[VarEvent]:
    return _get_defs_at_rec(node, varname, {node}, set())


def _get_defs_at_rec(
    node: nodes.NodeNG,
    varname: VarName,
    visited_nodes: Set[nodes.NodeNG],
    explored_functions: Set[nodes.NodeNG],
) -> List[VarEvent]:

    result = []

    root = node.root()
    calls_to_explore = set()
    loc = get_cfg_loc(node)
    block_kills = False
    # block_kills
    for i in range(loc.pos - 1, -1, -1):
        prev_loc = loc.block.locs[i]

        functions_to_explore = set()
        for var, event in prev_loc.var_events.all():
            if var.name == varname and event.type in KILLING_EVENTS:
                block_kills = True
                result.append(event)
            if isinstance(event.node.parent, nodes.Call) and event.node.parent.func == event.node:
                for def_ in event.definitions:
                    if isinstance(def_, nodes.FunctionDef):
                        functions_to_explore.add(def_.node)

        for call in get_calls(prev_loc.node):
            if not isinstance(call, nodes.Name):
                functions_to_explore.update(root.function_defs)

        all_functions_kill = True
        for function in functions_to_explore:
            for edge in function.args.cfg_loc.block.cfg.end.predecessors:
                predecessor = edge.source
                edge_kills = False
                for var, events in root.block_kills[predecessor].items():
                    if var.name == varname and scope_is_nested(loc.node.scope(), var.scope):
                        assert len(events) > 0
                        result.extend(events)
                        edge_kills = True
                all_functions_kill &= edge_kills
        block_kills |= len(functions_to_explore) > 0 and all_functions_kill

        if block_kills:
            break

    # preds kill
    all_preds_kill = True
    if not block_kills:
        for edge in loc.block.predecessors:
            predecessor = edge.source
            pred_kills = False
            for var, events in root.block_kills[predecessor].items():
                if var.name == varname:
                    result.extend(events)
                    pred_kills = True
            all_preds_kill &= pred_kills

    # calls kill
    if not all_preds_kill:
        while node is not None and not isinstance(node, nodes.FunctionDef):
            node = node.parent
        if node is not None:
            calls_to_explore.add(node)

    # unresolved calls
    end_nodes = root.unresolved_calls.copy() if len(calls_to_explore) > 0 else []

    for function in calls_to_explore:
        if function in explored_functions:
            continue

        explored_functions.add(function)
        # resolved calls
        var_events = list(function.cfg_loc.var_events.all())
        assert len(var_events) == 1 and var_events[0][0].name == function.name
        event = var_events[0][1]
        for use in event.uses:
            end_nodes.append(use.node)

        # made up calls
        if len(event.uses) == 0 or has_just_recursive_calls(root.call_graph, function):
            # make up consecutive calls
            for uncalled_function in get_uncalled_functions(root.function_defs, root.call_graph):
                for edge in uncalled_function.args.cfg_loc.block.cfg.end.predecessors:
                    predecessor = edge.source
                    for var, events in root.block_kills[predecessor].items():
                        if var.name == varname and scope_is_nested(
                            function.parent.scope(), var.scope
                        ):
                            assert len(events) > 0
                            result.extend(events)

            # prepare made up call at the end of scope
            assert len(function.parent.scope().cfg_loc.block.cfg.end.locs) == 0
            for edge in function.parent.scope().cfg_loc.block.cfg.end.predecessors:
                end_nodes.append(edge.source.locs[-1].node)

    for end_node in end_nodes:
        if end_node not in visited_nodes:
            visited_nodes.add(end_node)
            result.extend(_get_defs_at_rec(end_node, varname, visited_nodes, explored_functions))

    return result


def modified_in(vars: List[Variable], nodes: List[nodes.NodeNG]) -> bool:
    """Returns true iff any of the given variables is modified in given nodes (including syntactic children)."""
    # just check whether there is such an event
    for _ in get_events_for(vars, nodes, MODIFYING_EVENTS):
        return True
    return False


def get_vars_defined_before_core(core) -> Dict[int, Dict[Variable, Set[nodes.NodeNG]]]:
    # FIXME counts all read variables, including avars
    result = {}
    core = core if isinstance(core, list) else [core]
    for i in range(len(core[0].subs)):
        core_subs = [c.subs[i] for c in core]
        result[i] = get_vars_defined_before(core_subs)
    return result


def get_vars_defined_before(ns: List[nodes.NodeNG]) -> Dict[Variable, Set[nodes.NodeNG]]:
    result = defaultdict(set)
    check_parents = not all(hasattr(n, "cfg_loc") for n in ns)
    block = ns if not check_parents else [get_cfg_loc(ns[0]).node]
    children_locs = set(syntactic_children_locs(block))
    for loc in children_locs:
        for var, event in loc.var_events.all():
            if check_parents and event.node != ns[0] and ns[0] not in event.node.node_ancestors():
                continue
            for def_event in event.definitions:
                if get_cfg_loc(def_event.node) not in children_locs and (
                    not check_parents
                    or (def_event.node != ns[0] and ns[0] not in def_event.node.node_ancestors())
                ):
                    result[var].add(def_event.node)
    return result


def get_vars_used_after_core(core) -> Dict[int, Dict[Variable, Set[nodes.NodeNG]]]:
    """DANGER: variables used in core are not returned, even if core is in a loop"""
    result = {}
    core = core if isinstance(core, list) else [core]
    for i in range(len(core[0].subs)):
        core_subs = [c.subs[i] for c in core]
        result[i] = get_vars_used_after(core_subs)
    return result


def get_vars_used_after(ns: List[nodes.NodeNG]) -> Dict[Variable, Set[nodes.NodeNG]]:
    """DANGER: variables used in block are not returned, even if block is in a loop"""
    # TODO include only dominating uses
    result = defaultdict(set)
    check_parents = not all(hasattr(n, "cfg_loc") for n in ns)
    block = ns if not check_parents else [get_cfg_loc(ns[0]).node]
    children_locs = set(syntactic_children_locs(block))
    for loc in children_locs:
        for var, event in loc.var_events.all():
            if check_parents and event.node != ns[0] and ns[0] not in event.node.node_ancestors():
                continue
            for use_event in event.uses:
                if (
                    use_event.type not in (VarEventType.ASSIGN, VarEventType.REASSIGN)
                    and get_cfg_loc(use_event.node) not in children_locs
                    and (
                        not check_parents
                        or (
                            use_event.node != ns[0] and ns[0] not in use_event.node.node_ancestors()
                        )
                    )
                ):
                    result[var].add(use_event.node)
    return result


def get_control_statements(core):
    result = []
    first_loc = get_cfg_loc(core[0] if isinstance(core, list) else core)
    for loc in syntactic_children_locs_from(first_loc, core):
        if isinstance(loc.node, (nodes.Return, nodes.Break, nodes.Continue)):
            result.append(loc.node)
    return result


def scope_is_nested(inner, outer):
    if inner == outer:
        return True
    while inner.parent is not None:
        inner = inner.parent.scope()
        if inner == outer:
            return True
    return False


def scopes_are_nested(s1, s2):
    return scope_is_nested(s1, s2) or scope_is_nested(s2, s1)
