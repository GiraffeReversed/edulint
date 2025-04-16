from typing import List, Union, Set, Optional, Dict, Tuple, Iterator
from collections import defaultdict
from functools import lru_cache
from queue import deque
import heapq

from astroid import nodes

from edulint.linting.analyses.cfg.graph import CFGLoc, CFGBlock
from edulint.linting.analyses.cfg.utils import (
    successor_blocks_from_locs,
    successors_from_loc,
    predecessors_from_loc,
    syntactic_children_locs,
    syntactic_children_locs_from,
    get_cfg_loc,
)
from edulint.linting.analyses.var_events import (
    VarEventType,
    Variable,
    VarEvent,
    strip_to_name,
    ScopeNode,
)


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

    def collect_original_kills(
        var_to_index: Dict[Variable, int],
        index_to_block: List[CFGBlock],
        original_gens_kills,
        outside_scope_events,
        start_loc: CFGLoc,
    ):
        blocks = {}
        for block, _from, _to in successor_blocks_from_locs([start_loc], include_start=True):
            blocks[block] = len(blocks)
            index_to_block.append(block)
            gens, kill = defaultdict(list), defaultdict(list)
            for loc in block.locs:
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

                    if (
                        event.type == VarEventType.READ
                        and isinstance(event.node.parent, nodes.Call)
                        and event.node == event.node.parent.func
                    ):
                        possible_callees = [
                            callee
                            for callee in call_graph[event.node.scope()]
                            if isinstance(callee, nodes.FunctionDef) and callee.name == var.name
                        ]
                        assert len(possible_callees) <= 1
                        if len(possible_callees) == 0:
                            continue
                        called_fun = possible_callees[0]

                        for event in outside_scope_events[called_fun]:
                            in_call_var_i = var_to_index[event.var]
                            if event.type in GENERATING_EVENTS:
                                if len(kill[in_call_var_i]) == 0:
                                    gens[in_call_var_i].append(event)
                                else:
                                    for kill_event in kill[in_call_var_i][-1]:
                                        if kill_event not in event.definitions:
                                            event.definitions.append(kill_event)
                                            kill_event.uses.append(event)
                            if event.type in KILLING_EVENTS:
                                if len(kill[in_call_var_i]) > 0:
                                    for kill_event in kill[in_call_var_i][-1]:
                                        if kill_event not in event.redefines:
                                            event.redefines.append(kill_event)
                                            kill_event.redefined_by.append(event)
                                else:
                                    kill[in_call_var_i].append([])
                                kill[in_call_var_i][-1].append(event)

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

    def collect_kills_from_parents(computed_kills, all_parent_kills, blocks):
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

                for var_i, val in computed_kills[blocks[parent]].items():
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
            computed_kill = computed_kills[i]

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

    def make_up_calls(blocks, computed_kills, original_gens_kills):
        uncalled_functions = set(call_graph.keys()) - set(
            callee for callees in call_graph.values() for callee in callees
        )
        if len(uncalled_functions) == 0:
            return

        module_kills = defaultdict(list)
        for block, block_i in blocks.items():
            if any(len(edge.target.locs) == 0 for edge in block.successors):
                for var_i, val in computed_kills[block_i].items():
                    for index in ones_indices(val):
                        for kill_event in original_gens_kills[index][1][var_i][-1]:
                            module_kills[var_i].append(kill_event)

        gens = []
        kills = []
        for uncalled_fun in uncalled_functions:
            gens.append(defaultdict(list))
            kills.append(defaultdict(list))
            for event in outside_scope_events[uncalled_fun]:
                var_i = var_to_index[event.var]
                if event.type in GENERATING_EVENTS:
                    gens[-1][var_i].append(event)
                if event.type in KILLING_EVENTS:
                    kills[-1][var_i].append(event)

        for var_i in range(len(variables)):
            for kill in [module_kills] + kills:
                for kill_event in kill[var_i]:
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
    all_parent_kills = []

    for loc in [fun_def.args.cfg_loc for fun_def in function_defs] + [node.body[0].cfg_loc]:
        init_occupied_blocks = len(index_to_block)
        blocks = collect_original_kills(
            var_to_index, index_to_block, original_gens_kills, outside_scope_events, loc
        )
        computed_kills = []
        collect_computed_kills(original_gens_kills, computed_kills, blocks, init_occupied_blocks)
        collect_kills_from_parents(computed_kills, all_parent_kills, blocks)
        fixpoint(
            original_gens_kills, computed_kills, all_parent_kills, blocks, init_occupied_blocks
        )
    connect_events(index_to_block, all_parent_kills, original_gens_kills)
    # DANGER call relies on node.body[0].cfg_loc being the last processed
    make_up_calls(blocks, computed_kills, original_gens_kills)


def collect_reaching_definitions_(  # blocks
    node: nodes.Module,
) -> int:
    var_to_index = {}
    loc_to_block_index = {}
    index_to_block = []
    uncalled_defs = {}
    calls = defaultdict(list)

    # prepare
    def prepare():
        current_block = []
        for loc in successors_from_loc(
            node.cfg_loc, include_start=True, explore_functions=True, explore_classes=True
        ):
            has_call = False
            for var, events in loc.var_events.items():
                if var not in var_to_index:
                    var_to_index[var] = len(var_to_index)

                for event in events:
                    if event.type == VarEventType.ASSIGN and isinstance(
                        event.node, nodes.FunctionDef
                    ):
                        uncalled_defs[var] = event

                    if (
                        event.type == VarEventType.READ
                        and isinstance(event.node.parent, nodes.Call)
                        and event.node == event.node.parent.func
                    ):
                        calls[loc].append(var_to_index[var])
                        if var in uncalled_defs:
                            uncalled_defs.pop(var)
                        has_call = True

            if len(current_block) > 0 and current_block[-1].block != loc.block:
                index_to_block.append(current_block)
                current_block = []
            current_block.append(loc)
            loc_to_block_index[loc] = len(index_to_block)

            if has_call:
                index_to_block.append(current_block)
                current_block = []

        if len(current_block) > 0:
            index_to_block.append(current_block)

    prepare()

    # collect original kills
    def collect_original_kills():
        for block in index_to_block:
            gens, kill = defaultdict(list), defaultdict(list)
            for loc in block:
                for var, event in loc.var_events.all():
                    var_i = var_to_index[var]
                    if event.type in GENERATING_EVENTS:
                        if len(kill[var_i]) == 0:
                            gens[var_i].append(event)
                        else:
                            kill_event = kill[var_i][-1]

                            if kill_event not in event.definitions:
                                event.definitions.append(kill_event)
                                kill_event.uses.append(event)

                    if event.type in KILLING_EVENTS:
                        if len(kill[var_i]) > 0:
                            kill_event = kill[var_i][-1]
                            if kill_event not in event.redefines:
                                event.redefines.append(kill_event)
                                kill_event.redefined_by.append(event)
                        kill[var_i].append(event)

            original_gens_kills.append((gens, kill))

    original_gens_kills = []
    collect_original_kills()

    computed_kills = []

    def collect_computed_kills():
        for block_i in range(len(index_to_block)):
            _gens, kills = original_gens_kills[block_i]
            computed_kills.append(
                defaultdict(
                    int,
                    {var_i: 1 << block_i for var_i, events in kills.items() if len(events) > 0},
                )
            )

    collect_computed_kills()

    # kills from parents
    all_parent_kills = []

    def collect_kills_from_parents():
        for block in index_to_block:
            first_loc = block[0]
            if first_loc.pos > 0:
                pred_is = [loc_to_block_index[first_loc.block.locs[first_loc.pos - 1]]]
            else:
                pred_is = [
                    loc_to_block_index[edge.source.locs[-1]]
                    for edge in first_loc.block.predecessors
                    if edge.source.reachable and len(edge.source.locs) > 0
                ]

            result = defaultdict(int)
            for pred_i in pred_is:
                for var_i, val in computed_kills[pred_i].items():
                    result[var_i] |= val

            all_parent_kills.append(result)

    collect_kills_from_parents()

    # fixpoint
    def fixpoint_():  # does not work
        nonlocal var_to_index
        to_process = [[0]]
        visited = [False for _ in range(len(index_to_block))]
        visited[0] = True
        next_child = [0 for _ in range(len(index_to_block))]
        updates = [[] for _ in range(len(index_to_block))]

        call_stack = []
        function_in_kills = defaultdict(lambda: defaultdict(int))
        function_out_kills = defaultdict(lambda: defaultdict(int))
        while to_process:
            block_i = to_process[-1].pop()
            child_i = next_child[block_i]

            parent_kills = all_parent_kills[block_i]
            if child_i == 0:
                gens, original_kill = original_gens_kills[block_i]
                computed_kill = computed_kills[block_i]

                updated = []
                for var_i, val in parent_kills.items():
                    if computed_kill[var_i] != val and len(original_kill[var_i]) == 0:
                        computed_kill[var_i] = val
                        updated.append((var_i, val))
                updates[block_i].extend(updated)
            else:
                updated = updates[block_i]

            last_loc = index_to_block[block_i][-1]
            call_locs = []
            for call_var_i in calls[last_loc]:
                for kill_block_i in ones_indices(parent_kills[call_var_i]):
                    def_locs = [
                        event.node.args.cfg_loc
                        for event in original_gens_kills[kill_block_i][1][call_var_i]
                        if isinstance(event.node, nodes.FunctionDef)
                    ]
                    if len(def_locs) > 0:
                        call_locs.append(loc_to_block_index[def_locs[0]])
            if len(call_locs) > 0:
                succ_block_is = call_locs
                call_stack.append(last_loc)
            elif last_loc.pos < len(last_loc.block.locs) - 1:
                succ_block_is = [loc_to_block_index[last_loc.block.locs[last_loc.pos + 1]]]
            else:
                succ_block_is = [
                    loc_to_block_index[edge.target.locs[0]]
                    for edge in last_loc.block.successors
                    if len(edge.target.locs) > 0
                ]

            if len(succ_block_is) == 0:
                if len(call_stack) > 0:
                    caller_loc = call_stack.pop()
                    if caller_loc.pos < len(caller_loc.block.locs) - 1:
                        succ_block_is = [
                            loc_to_block_index[caller_loc.block.locs[caller_loc.pos + 1]]
                        ]
                    else:
                        succ_block_is = [
                            loc_to_block_index[edge.target.locs[0]]
                            for edge in caller_loc.block.successors
                            if len(edge.target.locs) > 0
                        ]
                else:
                    succ_block_is = [
                        loc_to_block_index[event.node.args.cfg_loc]
                        for event in uncalled_defs.values()
                    ]

            if child_i >= len(succ_block_is):
                updates[block_i] = []
                continue

            to_process.append(block_i)
            next_child[block_i] += 1

            added = False
            succ_i = succ_block_is[child_i]
            child_kills = all_parent_kills[succ_i]
            for var_i, val in updated:
                if val & child_kills[var_i] != val:
                    child_kills[var_i] |= val
                    if succ_i not in to_process:
                        to_process.append(succ_i)
                        visited[succ_i] = True
                    next_child[succ_i] = 0
                    added = True

            if not added and not visited[succ_i]:
                to_process.append(succ_i)
                visited[succ_i] = True

    def fixpoint():
        to_process = deque(range(len(index_to_block)))
        call_stack = []
        while to_process:
            block_i = to_process.popleft()
            parent_kills = all_parent_kills[block_i]
            gens, original_kill = original_gens_kills[block_i]
            computed_kill = computed_kills[block_i]

            updated = []
            for var_i, val in parent_kills.items():
                if computed_kill[var_i] != val and len(original_kill[var_i]) == 0:
                    computed_kill[var_i] = val
                    updated.append((var_i, val))

            last_loc = index_to_block[block_i][-1]
            call_locs = []
            for call_var_i in calls[last_loc]:
                for kill_block_i in ones_indices(parent_kills[call_var_i]):
                    def_locs = [
                        event.node.args.cfg_loc
                        for event in original_gens_kills[kill_block_i][1][call_var_i]
                        if isinstance(event.node, nodes.FunctionDef)
                    ]
                    if len(def_locs) > 0:
                        call_locs.append(loc_to_block_index[def_locs[0]])
            if len(call_locs) > 0:
                succ_block_is = call_locs
                call_stack.append(last_loc)
            elif last_loc.pos < len(last_loc.block.locs) - 1:
                succ_block_is = [loc_to_block_index[last_loc.block.locs[last_loc.pos + 1]]]
            else:
                succ_block_is = [
                    loc_to_block_index[edge.target.locs[0]]
                    for edge in last_loc.block.successors
                    if len(edge.target.locs) > 0
                ]

            if len(succ_block_is) == 0:
                if len(call_stack) > 0:
                    caller_loc = call_stack.pop()
                    if caller_loc.pos < len(caller_loc.block.locs) - 1:
                        succ_block_is = [
                            loc_to_block_index[caller_loc.block.locs[caller_loc.pos + 1]]
                        ]
                    else:
                        succ_block_is = [
                            loc_to_block_index[edge.target.locs[0]]
                            for edge in caller_loc.block.successors
                            if len(edge.target.locs) > 0
                        ]
                else:
                    succ_block_is = [
                        loc_to_block_index[event.node.args.cfg_loc]
                        for event in uncalled_defs.values()
                    ]

            for succ_i in succ_block_is:
                child_kills = all_parent_kills[succ_i]
                for var_i, val in updated:
                    if val & child_kills[var_i] != val:
                        child_kills[var_i] |= val
                        if succ_i not in to_process:
                            to_process.append(succ_i)

    fixpoint()

    # connect events
    def connect_events():
        for block_i in range(len(index_to_block)):
            parent_kills = all_parent_kills[block_i]
            gens, original_kill = original_gens_kills[block_i]

            for var_i, val in parent_kills.items():
                if len(gens[var_i]) == 0 and len(original_kill[var_i]) == 0:
                    continue

                for index in ones_indices(val):
                    kill_event = original_gens_kills[index][1][var_i][-1]

                    if len(original_kill[var_i]) > 0:
                        other_kill_event = original_kill[var_i][0]
                        kill_event.redefined_by.append(other_kill_event)
                        other_kill_event.redefines.append(kill_event)

                    for gen_event in gens[var_i]:
                        gen_event.definitions.append(kill_event)
                        kill_event.uses.append(gen_event)

    connect_events()


def collect_reaching_definitions_(  # locs opt
    node: Union[nodes.Module, nodes.Arguments],
) -> int:
    index_to_loc = []
    var_to_index = {}
    defs = {}
    calls = defaultdict(list)

    # prepare
    def prepare():
        for loc in successors_from_loc(
            node.cfg_loc, include_start=True, explore_functions=True, explore_classes=True
        ):
            index_to_loc.append(loc)

            for var, events in loc.var_events.items():
                if var not in var_to_index:
                    var_to_index[var] = len(var_to_index)

                for event in events:
                    if event.type == VarEventType.ASSIGN and isinstance(
                        event.node, nodes.FunctionDef
                    ):
                        defs[var] = event

                    if (
                        event.type == VarEventType.READ
                        and isinstance(event.node.parent, nodes.Call)
                        and event.node == event.node.parent.func
                    ):
                        calls[loc].append(var_to_index[var])
                        if var in defs:
                            defs.pop(var)

    prepare()
    loc_to_index = {loc: i for i, loc in enumerate(index_to_loc)}

    # collect original kills
    original_gens_kills = []

    def collect_original_kills():
        for loc in index_to_loc:
            gens, kill = defaultdict(list), defaultdict(list)
            for var, event in loc.var_events.all():
                var_i = var_to_index[var]
                if event.type in GENERATING_EVENTS:
                    if len(kill[var_i]) == 0:
                        gens[var_i].append(event)

                if event.type in KILLING_EVENTS:
                    kill[var_i].append(event)

            original_gens_kills.append((gens, kill))

    collect_original_kills()

    computed_kills = []

    def collect_computed_kills():
        for loc_i in range(len(index_to_loc)):
            _gens, kills = original_gens_kills[loc_i]
            computed_kills.append(
                defaultdict(
                    int,
                    {var_i: 1 << loc_i for var_i, events in kills.items() if len(events) > 0},
                )
            )

    collect_computed_kills()

    # kills from parents
    def collect_parent_kills(filter):
        for loc_i, loc in enumerate(index_to_loc):
            if loc.pos > 0:
                pred_is = [loc_to_index[loc.block.locs[loc.pos - 1]]]
            else:
                pred_is = [
                    loc_to_index[edge.source.locs[-1]]
                    for edge in loc.block.predecessors
                    if edge.source.reachable and len(edge.source.locs) > 0
                ]

            result = defaultdict(int)
            _gens, original_kill = original_gens_kills[loc_i]
            computed_kill = computed_kills[loc_i]
            for pred_i in pred_is:
                for var_i, val in computed_kills[pred_i].items():
                    if not filter or computed_kill[var_i] != val and len(original_kill[var_i]) == 0:
                        result[var_i] |= val

            all_parent_kills.append(result)

    all_parent_kills = []
    collect_parent_kills(filter=True)

    # fixpoint
    def fixpoint():
        nonlocal var_to_index
        to_process = deque(loc_i for loc_i in range(len(index_to_loc)))
        all_callee_locs = defaultdict(list)
        call_stack = []
        while to_process:
            loc_i = to_process.popleft()
            loc = index_to_loc[loc_i]
            parent_kills = all_parent_kills[loc_i]
            # gens, original_kill = original_gens_kills[loc_i]
            computed_kill = computed_kills[loc_i]

            updated = []
            for var_i, val in parent_kills.items():
                computed_kill[var_i] |= val
                updated.append((var_i, val))

            all_callee_locs[loc_i].extend(
                [
                    index_to_loc[kill_i].node.args.cfg_loc
                    for call_var_i in calls[loc]
                    for kill_i in ones_indices(parent_kills[call_var_i])
                    if isinstance(index_to_loc[kill_i].node, nodes.FunctionDef)
                ]
            )
            parent_kills.clear()
            if len(updated) == 0:
                continue

            callee_locs = all_callee_locs[loc_i]
            if len(callee_locs) > 0:
                succ_locs = callee_locs
                call_stack.append(loc)
            elif loc.pos < len(loc.block.locs) - 1:
                succ_locs = [loc.block.locs[loc.pos + 1]]
            else:
                succ_locs = [
                    edge.target.locs[0]
                    for edge in loc.block.successors
                    if len(edge.target.locs) > 0
                ]

            if len(succ_locs) == 0:
                if len(call_stack) > 0:
                    caller_loc = call_stack.pop()
                    if caller_loc.pos < len(caller_loc.block.locs) - 1:
                        succ_locs = [caller_loc.block.locs[caller_loc.pos + 1]]
                    else:
                        succ_locs = [
                            edge.target.locs[0]
                            for edge in caller_loc.block.successors
                            if len(edge.target.locs) > 0
                        ]
                else:
                    succ_locs = [event.node.args.cfg_loc for event in defs.values()]

            for succ_loc in succ_locs:
                succ_i = loc_to_index[succ_loc]
                child_parent_kills = all_parent_kills[succ_i]
                child_computed_kills = computed_kills[succ_i]
                child_original_kills = original_gens_kills[succ_i][1]
                for var_i, val in updated:
                    if (
                        val & child_computed_kills[var_i] != val
                        and len(child_original_kills[var_i]) == 0
                    ):
                        child_parent_kills[var_i] |= val
                        if succ_i not in to_process:
                            to_process.append(succ_i)

    fixpoint()

    all_parent_kills = []
    collect_parent_kills(filter=False)

    # connect events
    def connect_events():
        for loc, loc_i in loc_to_index.items():
            parent_kills = all_parent_kills[loc_i]
            gens, original_kill = original_gens_kills[loc_i]

            for var_i, val in parent_kills.items():
                if len(gens[var_i]) == 0 and len(original_kill[var_i]) == 0:
                    continue

                for index in ones_indices(val):
                    kill_event = original_gens_kills[index][1][var_i][-1]

                    if len(original_kill[var_i]) > 0:
                        other_kill_event = original_kill[var_i][0]
                        kill_event.redefined_by.append(other_kill_event)
                        other_kill_event.redefines.append(kill_event)

                    for gen_event in gens[var_i]:
                        gen_event.definitions.append(kill_event)
                        kill_event.uses.append(gen_event)

    connect_events()


def collect_reaching_definitions_(  # locs
    node: Union[nodes.Module, nodes.Arguments],
) -> int:
    index_to_loc = []
    var_to_index = {}
    defs = {}
    calls = defaultdict(list)

    # prepare
    def prepare():
        for loc in successors_from_loc(
            node.cfg_loc, include_start=True, explore_functions=True, explore_classes=True
        ):
            index_to_loc.append(loc)

            for var, events in loc.var_events.items():
                if var not in var_to_index:
                    var_to_index[var] = len(var_to_index)

                for event in events:
                    if event.type == VarEventType.ASSIGN and isinstance(
                        event.node, nodes.FunctionDef
                    ):
                        defs[var] = event

                    if (
                        event.type == VarEventType.READ
                        and isinstance(event.node.parent, nodes.Call)
                        and event.node == event.node.parent.func
                    ):
                        calls[loc].append(var_to_index[var])
                        if var in defs:
                            defs.pop(var)

    prepare()
    loc_to_index = {loc: i for i, loc in enumerate(index_to_loc)}

    # collect original kills
    original_gens_kills = []

    def collect_original_kills():
        for loc in index_to_loc:
            gens, kill = defaultdict(list), defaultdict(list)
            for var, event in loc.var_events.all():
                var_i = var_to_index[var]
                if event.type in GENERATING_EVENTS:
                    if len(kill[var_i]) == 0:
                        gens[var_i].append(event)

                if event.type in KILLING_EVENTS:
                    kill[var_i].append(event)

            original_gens_kills.append((gens, kill))

    collect_original_kills()

    computed_kills = []

    def collect_computed_kills():
        for loc_i in range(len(index_to_loc)):
            _gens, kills = original_gens_kills[loc_i]
            computed_kills.append(
                defaultdict(
                    int,
                    {var_i: 1 << loc_i for var_i, events in kills.items() if len(events) > 0},
                )
            )

    collect_computed_kills()

    # kills from parents
    all_parent_kills = []

    def collect_parent_kills():
        for loc_i, loc in enumerate(index_to_loc):
            if loc.pos > 0:
                pred_is = [loc_to_index[loc.block.locs[loc.pos - 1]]]
            else:
                pred_is = [
                    loc_to_index[edge.source.locs[-1]]
                    for edge in loc.block.predecessors
                    if edge.source.reachable and len(edge.source.locs) > 0
                ]

            result = defaultdict(int)
            for pred_i in pred_is:
                for var_i, val in computed_kills[pred_i].items():
                    result[var_i] |= val

            all_parent_kills.append(result)

    collect_parent_kills()

    # fixpoint
    def fixpoint():
        to_process = deque(loc_i for loc_i in range(len(index_to_loc)))
        # to_process = deque({(0, index_to_loc[0])})
        # visited = [False for _ in range(len(index_to_loc))]
        # visited[0] = True
        call_stack = []
        while to_process:
            loc_i = to_process.popleft()
            loc = index_to_loc[loc_i]
            parent_kills = all_parent_kills[loc_i]
            gens, original_kill = original_gens_kills[loc_i]
            computed_kill = computed_kills[loc_i]

            updated = []
            for var_i, val in parent_kills.items():
                if computed_kill[var_i] != val and len(original_kill[var_i]) == 0:
                    computed_kill[var_i] = val
                    updated.append((var_i, val))

            callee_locs = [
                index_to_loc[kill_i].node.args.cfg_loc
                for call_var_i in calls[loc]
                for kill_i in ones_indices(parent_kills[call_var_i])
                if isinstance(index_to_loc[kill_i].node, nodes.FunctionDef)
            ]
            if len(callee_locs) > 0:
                succ_locs = callee_locs
                call_stack.append(loc)
            elif loc.pos < len(loc.block.locs) - 1:
                succ_locs = [loc.block.locs[loc.pos + 1]]
            else:
                succ_locs = [
                    edge.target.locs[0]
                    for edge in loc.block.successors
                    if len(edge.target.locs) > 0
                ]

            if len(succ_locs) == 0:
                if len(call_stack) > 0:
                    caller_loc = call_stack.pop()
                    if caller_loc.pos < len(caller_loc.block.locs) - 1:
                        succ_locs = [caller_loc.block.locs[caller_loc.pos + 1]]
                    else:
                        succ_locs = [
                            edge.target.locs[0]
                            for edge in caller_loc.block.successors
                            if len(edge.target.locs) > 0
                        ]
                else:
                    succ_locs = [event.node.args.cfg_loc for event in defs.values()]

            for succ_loc in succ_locs:
                succ_i = loc_to_index[succ_loc]
                child_kills = all_parent_kills[succ_i]
                for var_i, val in updated:
                    if val & child_kills[var_i] != val:
                        child_kills[var_i] |= val
                        if succ_i not in to_process:
                            to_process.append(succ_i)
                #             visited[succ_i] = True
                # if len(updated) == 0 and not visited[succ_i]:
                #     to_process.append((succ_i, succ_loc))
                #     visited[succ_i] = True

    fixpoint()

    # connect events
    def connect_events():
        for loc, loc_i in loc_to_index.items():
            parent_kills = all_parent_kills[loc_i]
            gens, original_kill = original_gens_kills[loc_i]

            for var_i, val in parent_kills.items():
                if len(gens[var_i]) == 0 and len(original_kill[var_i]) == 0:
                    continue

                for index in ones_indices(val):
                    kill_event = original_gens_kills[index][1][var_i][-1]

                    if len(original_kill[var_i]) > 0:
                        other_kill_event = original_kill[var_i][0]
                        kill_event.redefined_by.append(other_kill_event)
                        other_kill_event.redefines.append(kill_event)

                    for gen_event in gens[var_i]:
                        gen_event.definitions.append(kill_event)
                        kill_event.uses.append(gen_event)

    connect_events()


def collect_reaching_definitions_(  # all indices opt no block passing dict computed kills yes calls
    node: Union[nodes.Module, nodes.Arguments],
    occupied_blocks: int = 0,
    all_vars: Optional[Dict[Variable, int]] = None,
    original_gens_kills: Optional[
        List[Tuple[Dict[Variable, List[VarEvent]], Dict[Variable, List[VarEvent]]]]
    ] = None,
    parent_scope_kills: Dict[Variable, List[VarEvent]] = None,
) -> int:
    init_occupied_blocks = occupied_blocks
    all_vars = all_vars if all_vars is not None else {}
    original_gens_kills = original_gens_kills if original_gens_kills else []
    parent_scope_kills = parent_scope_kills if parent_scope_kills is not None else {}

    blocks = {}

    # prepare
    def prepare():
        for block, start, end in successor_blocks_from_locs([node.cfg_loc], include_start=True):
            assert start == 0 and end == len(block.locs)
            blocks[block] = len(blocks)

            for loc in block.locs:
                for var in loc.var_events:
                    if var not in all_vars:
                        all_vars[var] = len(all_vars)

    prepare()

    # for block in blocks:
    #     block == block

    occupied_blocks += len(blocks)

    # collect original kills
    def collect_original_kills():
        for block in blocks.keys():
            gens, kill = defaultdict(list), defaultdict(list)
            for loc in block.locs:
                for var, event in loc.var_events.all():
                    var_i = all_vars[var]
                    if event.type in GENERATING_EVENTS:
                        if len(kill[var_i]) == 0:
                            gens[var_i].append(event)
                        else:
                            kill_event = kill[var_i][-1]

                            if kill_event not in event.definitions:
                                event.definitions.append(kill_event)
                                kill_event.uses.append(event)

                    if event.type in KILLING_EVENTS:
                        if len(kill[var_i]) > 0:
                            kill_event = kill[var_i][-1]
                            if kill_event not in event.redefines:
                                event.redefines.append(kill_event)
                                kill_event.redefined_by.append(event)
                        kill[var_i].append(event)

            original_gens_kills.append((gens, kill))

    collect_original_kills()

    computed_kills = []

    def collect_computed_kills():
        for block_i in range(len(blocks)):
            _gens, kills = original_gens_kills[init_occupied_blocks + block_i]
            computed_kills.append(
                defaultdict(
                    int,
                    {
                        var_i: 1 << (init_occupied_blocks + block_i)
                        for var_i, events in kills.items()
                        if len(events) > 0
                    },
                )
            )

    collect_computed_kills()

    # kills from parents
    all_parent_kills = []

    def collect_kills_from_parents():
        for block in blocks.keys():
            if len(block.predecessors) == 0:
                all_parent_kills.append(parent_scope_kills)
                continue

            result = defaultdict(int)
            for edge in block.predecessors:
                parent = edge.source
                if not parent.reachable:
                    continue

                for var_i, val in computed_kills[blocks[parent]].items():
                    result[var_i] |= val

            all_parent_kills.append(result)

    collect_kills_from_parents()

    # fixpoint
    def fixpoint():
        to_process = deque(enumerate(blocks.keys()))
        while to_process:
            i, block = to_process.popleft()
            parent_kills = all_parent_kills[i]
            gens, original_kill = original_gens_kills[init_occupied_blocks + i]
            computed_kill = computed_kills[i]

            updated = []
            for var_i, val in parent_kills.items():
                if computed_kill[var_i] != val and len(original_kill[var_i]) == 0:
                    computed_kill[var_i] = val
                    updated.append((var_i, val))

            for edge in block.successors:
                if len(edge.target.locs) == 0:
                    continue
                j = blocks[edge.target]
                child_kills = all_parent_kills[j]
                for var_i, val in updated:
                    if val & child_kills[var_i] != val:
                        child_kills[var_i] |= val
                        if (j, edge.target) not in to_process:
                            to_process.append((j, edge.target))

    fixpoint()

    # nest
    def nest():
        nonlocal occupied_blocks
        for i, block in enumerate(blocks.keys()):
            for loc in block.locs:
                if isinstance(loc.node, nodes.FunctionDef):
                    occupied_blocks = collect_reaching_definitions(
                        loc.node.args,
                        occupied_blocks,
                        all_vars,
                        original_gens_kills,
                        computed_kills[i],
                    )
                elif isinstance(loc.node, nodes.ClassDef):
                    for class_node in loc.node.body:
                        if isinstance(class_node, nodes.FunctionDef):
                            occupied_blocks = collect_reaching_definitions(
                                class_node.args,
                                occupied_blocks,
                                all_vars,
                                original_gens_kills,
                                computed_kills[i],
                            )

    nest()

    # connect events
    def connect_events():
        for i, block in enumerate(blocks.keys()):
            parent_kills = all_parent_kills[i]
            gens, original_kill = original_gens_kills[init_occupied_blocks + i]

            for var_i, val in parent_kills.items():
                if len(gens[var_i]) == 0 and len(original_kill[var_i]) == 0:
                    continue

                for index in ones_indices(val):
                    kill_event = original_gens_kills[index][1][var_i][-1]

                    if len(original_kill[var_i]) > 0:
                        other_kill_event = original_kill[var_i][0]
                        kill_event.redefined_by.append(other_kill_event)
                        other_kill_event.redefines.append(kill_event)

                    for gen_event in gens[var_i]:
                        gen_event.definitions.append(kill_event)
                        kill_event.uses.append(gen_event)

    connect_events()

    return occupied_blocks


def collect_reaching_definitions_(  # all indices opt no block passing dict computed kills no calls
    node: Union[nodes.Module, nodes.Arguments],
    occupied_blocks: int = 0,
    all_vars: Optional[Dict[Variable, int]] = None,
    original_gens_kills: Optional[
        List[Tuple[Dict[Variable, List[VarEvent]], Dict[Variable, List[VarEvent]]]]
    ] = None,
    parent_scope_kills: Dict[Variable, List[VarEvent]] = None,
) -> int:
    init_occupied_blocks = occupied_blocks
    all_vars = all_vars if all_vars is not None else {}
    original_gens_kills = original_gens_kills if original_gens_kills else []
    parent_scope_kills = parent_scope_kills if parent_scope_kills is not None else {}

    blocks = {}

    # prepare
    for block, start, end in successor_blocks_from_locs([node.cfg_loc], include_start=True):
        assert start == 0 and end == len(block.locs)
        blocks[block] = len(blocks)

        for loc in block.locs:
            for var in loc.var_events:
                if var not in all_vars:
                    all_vars[var] = len(all_vars)

    occupied_blocks += len(blocks)

    # collect original kills
    for block in blocks.keys():
        gens, kill = defaultdict(list), defaultdict(list)
        for loc in block.locs:
            for var, event in loc.var_events.all():
                var_i = all_vars[var]
                if event.type in GENERATING_EVENTS:
                    if len(kill[var_i]) == 0:
                        gens[var_i].append(event)
                    else:
                        kill_event = kill[var_i][-1]

                        if kill_event not in event.definitions:
                            event.definitions.append(kill_event)
                            kill_event.uses.append(event)

                if event.type in KILLING_EVENTS:
                    if len(kill[var_i]) > 0:
                        kill_event = kill[var_i][-1]
                        if kill_event not in event.redefines:
                            event.redefines.append(kill_event)
                            kill_event.redefined_by.append(event)
                    kill[var_i].append(event)

        original_gens_kills.append((gens, kill))

    computed_kills = []
    for block_i in range(len(blocks)):
        _gens, kills = original_gens_kills[init_occupied_blocks + block_i]
        computed_kills.append(
            defaultdict(
                int,
                {
                    var_i: 1 << (init_occupied_blocks + block_i)
                    for var_i, events in kills.items()
                    if len(events) > 0
                },
            )
        )

    # kills from parents
    all_parent_kills = []
    for block in blocks.keys():
        if len(block.predecessors) == 0:
            all_parent_kills.append(parent_scope_kills)
            continue

        result = defaultdict(int)
        for edge in block.predecessors:
            parent = edge.source
            if not parent.reachable:
                continue

            for var_i, val in computed_kills[blocks[parent]].items():
                result[var_i] |= val

        all_parent_kills.append(result)

    # fixpoint
    to_process = deque(enumerate(blocks.keys()))
    while to_process:
        i, block = to_process.popleft()
        parent_kills = all_parent_kills[i]
        gens, original_kill = original_gens_kills[init_occupied_blocks + i]
        computed_kill = computed_kills[i]

        updated = []
        for var_i, val in parent_kills.items():
            if computed_kill[var_i] != val and len(original_kill[var_i]) == 0:
                computed_kill[var_i] = val
                updated.append((var_i, val))

        for edge in block.successors:
            if len(edge.target.locs) == 0:
                continue
            j = blocks[edge.target]
            child_kills = all_parent_kills[j]
            for var_i, val in updated:
                if val & child_kills[var_i] != val:
                    child_kills[var_i] |= val
                    if (j, edge.target) not in to_process:
                        to_process.append((j, edge.target))

    # nest
    for i, block in enumerate(blocks.keys()):
        for loc in block.locs:
            if isinstance(loc.node, nodes.FunctionDef):
                occupied_blocks = collect_reaching_definitions(
                    loc.node.args,
                    occupied_blocks,
                    all_vars,
                    original_gens_kills,
                    computed_kills[i],
                )
            elif isinstance(loc.node, nodes.ClassDef):
                for class_node in loc.node.body:
                    if isinstance(class_node, nodes.FunctionDef):
                        occupied_blocks = collect_reaching_definitions(
                            class_node.args,
                            occupied_blocks,
                            all_vars,
                            original_gens_kills,
                            computed_kills[i],
                        )

    # connect events
    for i, block in enumerate(blocks.keys()):
        parent_kills = all_parent_kills[i]
        gens, original_kill = original_gens_kills[init_occupied_blocks + i]

        for var_i, val in parent_kills.items():
            if len(gens[var_i]) == 0 and len(original_kill[var_i]) == 0:
                continue

            for index in ones_indices(val):
                kill_event = original_gens_kills[index][1][var_i][-1]

                if len(original_kill[var_i]) > 0:
                    other_kill_event = original_kill[var_i][0]
                    kill_event.redefined_by.append(other_kill_event)
                    other_kill_event.redefines.append(kill_event)

                for gen_event in gens[var_i]:
                    gen_event.definitions.append(kill_event)
                    kill_event.uses.append(gen_event)

    return occupied_blocks


def collect_reaching_definitions_(  # old
    node: Union[nodes.Module, nodes.Arguments],
    parent_scope_kills: Dict[Variable, List[VarEvent]] = None,
) -> None:
    parent_scope_kills = parent_scope_kills if parent_scope_kills is not None else {}

    original_gens_kills = []
    blocks = []

    def collect_original_kills():
        for block, start, end in successor_blocks_from_locs([node.cfg_loc], include_start=True):
            assert start == 0 and end == len(block.locs)
            original_gens_kills.append(collect_gens_kill(block))

            blocks.append(block)

    collect_original_kills()

    computed_kills = {
        blocks[i]: defaultdict(list, {var: k[-1:] for var, k in kills.items()})
        for i, (_gens, kills) in enumerate(original_gens_kills)
    }

    def kills_from_parents(
        block: CFGBlock,
        kills: Dict[CFGBlock, Dict[Variable, List[VarEvent]]],
        parent_scope_kills: Dict[Variable, List[VarEvent]],
    ) -> Dict[Variable, List[VarEvent]]:
        if len(block.predecessors) == 0:
            return parent_scope_kills

        # result = defaultdict(dict)
        result = defaultdict(list)
        for edge in block.predecessors:
            parent = edge.source
            if not parent.reachable:
                continue
            for var, es in kills[parent].items():
                # result[var].extend(es)
                for e in es:
                    if e not in result[var]:
                        result[var].append(e)
                # for e in es:
                #     result[var][e.node.col_offset] = e
        # return {var: list(es.values()) for var, es in result.items()}
        return result

    # def fixpoint():
    #     changed = True
    #     while changed:
    #         changed = False

    #         for i, block in enumerate(blocks):
    #             parent_kills = kills_from_parents(block, computed_kills, parent_scope_kills)
    #             gens, original_kill = original_gens_kills[i]
    #             computed_kill = computed_kills[block]

    #             for var, es in parent_kills.items():
    #                 # this block does not kill the parent's value
    #                 if var not in original_kill:
    #                     for kill_event in es:
    #                         # if the kill was not added already
    #                         if kill_event not in computed_kill[var]:
    #                             computed_kill[var].append(kill_event)
    #                             changed = True

    def fixpoint():
        to_process = deque(enumerate(blocks))
        while to_process:
            i, block = to_process.popleft()
            # for block in blocks:
            parent_kills = kills_from_parents(block, computed_kills, parent_scope_kills)
            gens, original_kill = original_gens_kills[i]
            computed_kill = computed_kills[block]

            changed = False
            for var, es in parent_kills.items():
                # this block does not kill the parent's value
                if var not in original_kill:
                    for kill_event in es:
                        # if the kill was not added already
                        if kill_event not in computed_kill[var]:
                            computed_kill[var].append(kill_event)
                            changed = True

            if changed:
                to_process.extend(
                    [
                        (blocks.index(edge.target), edge.target)
                        for edge in block.successors
                        if len(edge.target.locs) > 0
                    ]
                )

    fixpoint()

    def nest():
        for block in blocks:
            for loc in block.locs:
                if isinstance(loc.node, nodes.FunctionDef):
                    collect_reaching_definitions(loc.node.args, computed_kills[block])
                elif isinstance(loc.node, nodes.ClassDef):
                    for class_node in loc.node.body:
                        if isinstance(class_node, nodes.FunctionDef):
                            collect_reaching_definitions(class_node.args, computed_kills[block])

    nest()

    def connect_events():
        for i, block in enumerate(blocks):
            parent_kills = kills_from_parents(block, computed_kills, parent_scope_kills)
            gens, original_kill = original_gens_kills[i]

            for var, es in parent_kills.items():
                if var not in gens and var not in original_kill:
                    continue
                for kill_event in es:
                    if var in original_kill:
                        other_kill_event = original_kill[var][0]
                        # if other_kill_event not in kill_event.redefined_by:
                        kill_event.redefined_by.append(other_kill_event)
                        other_kill_event.redefines.append(kill_event)

                    for gen_event in gens[var]:
                        # if kill_event not in gen_event.definitions:
                        gen_event.definitions.append(kill_event)
                        kill_event.uses.append(gen_event)

    connect_events()


def collect_reaching_definitions_(  # original
    node: Union[nodes.Module, nodes.Arguments],
    parent_scope_kills: Dict[Variable, List[VarEvent]] = None,
) -> None:

    def kills_from_parents_original(
        block: CFGBlock,
        kills: Dict[CFGBlock, Dict[Variable, List[VarEvent]]],
        parent_scope_kills: Dict[Variable, List[VarEvent]],
    ) -> Dict[Variable, List[VarEvent]]:
        if len(block.predecessors) == 0:
            return parent_scope_kills

        result = defaultdict(list)
        for edge in block.predecessors:
            parent = edge.source
            if not parent.reachable:
                continue
            for var, es in kills[parent].items():
                result[var].extend(es)
        return result

    parent_scope_kills = parent_scope_kills if parent_scope_kills is not None else {}

    original_gens_kills = {}
    blocks = []
    for block, start, end in successor_blocks_from_locs([node.cfg_loc], include_start=True):
        assert start == 0 and end == len(block.locs)
        original_gens_kills[block] = collect_gens_kill(block)

        blocks.append(block)

    computed_kills = {
        block: defaultdict(list, {var: k.copy() for var, k in kills.items()})
        for block, (_gens, kills) in original_gens_kills.items()
    }

    changed = True
    while changed:
        changed = False

        for block in blocks:
            parent_kills = kills_from_parents_original(block, computed_kills, parent_scope_kills)
            gens, original_kill = original_gens_kills[block]
            computed_kill = computed_kills[block]

            for var, es in parent_kills.items():
                for kill_event in es:
                    # this block does not kill the parent's value
                    if var not in original_kill:
                        # if the kill was not added already
                        if kill_event not in computed_kill[var]:
                            computed_kill[var].append(kill_event)
                            changed = True
                    else:
                        other_kill_event = original_kill[var][0]
                        if other_kill_event not in kill_event.redefined_by:
                            kill_event.redefined_by.append(other_kill_event)
                            other_kill_event.redefines.append(kill_event)

                    for gen_event in gens.get(var, []):
                        if kill_event not in gen_event.definitions:
                            gen_event.definitions.append(kill_event)
                            kill_event.uses.append(gen_event)

    for block in blocks:
        for loc in block.locs:
            if isinstance(loc.node, nodes.FunctionDef):
                collect_reaching_definitions(loc.node.args, computed_kills[block])
            elif isinstance(loc.node, nodes.ClassDef):
                for class_node in loc.node.body:
                    if isinstance(class_node, nodes.FunctionDef):
                        collect_reaching_definitions(class_node.args, computed_kills[block])


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


def node_to_event(node: nodes.NodeNG) -> Optional[VarEvent]:
    """Returns event related to given node, if such exists."""
    loc = get_cfg_loc(node)
    for var, event in loc.var_events.all():
        if event.node == node:
            return event
    return None


def node_to_var(node: nodes.NodeNG):
    """Returns variable related to given node, if such exists."""
    event = node_to_event(node)
    return event.var if event is not None else None


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
_ASSIGNING_PARENT_STATEMENTS = (nodes.Arguments, nodes.With, nodes.ExceptHandler)


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


def modified_in(vars: List[Variable], nodes: List[nodes.NodeNG]) -> bool:
    """Returns true iff any of the given variables is modified in given nodes (including syntactic children)."""
    # just check whether there is such an event
    for _ in get_events_for(vars, nodes, MODIFYING_EVENTS):
        return True
    return False


def get_vars_defined_before(core) -> Dict[Variable, Set[nodes.NodeNG]]:
    # FIXME counts all read variables, including avars
    result = defaultdict(set)
    for i in range(len(core[0].sub_locs)):
        core_sub_locs = [c.sub_locs[i] for c in core]
        children_locs = set(
            syntactic_children_locs_from(core_sub_locs[0], [loc.node for loc in core_sub_locs])
        )
        for loc in children_locs:
            for var, event in loc.var_events.all():
                # if event.type not in GENERATING_EVENTS:
                #     continue
                for def_event in event.definitions:
                    if get_cfg_loc(def_event.node) not in children_locs:
                        result[var].add(def_event.node)
    return result


def get_vars_used_after(core) -> Dict[Variable, Set[nodes.NodeNG]]:
    """DANGER: variables used in core are not returned, even if core is in a loop"""
    result = defaultdict(set)
    for i in range(len(core[0].sub_locs)):
        core_sub_locs = [c.sub_locs[i] for c in core]
        children_locs = set(
            syntactic_children_locs_from(core_sub_locs[0], [loc.node for loc in core_sub_locs])
        )
        for loc in children_locs:
            for var, event in loc.var_events.all():
                # if event.type not in MODIFYING_EVENTS:
                #     continue
                for use_event in event.uses:
                    if get_cfg_loc(use_event.node) not in children_locs:
                        result[var].add(use_event.node)
    return result


def get_control_statements(core):
    result = []
    first_loc = get_cfg_loc(core[0] if isinstance(core, list) else core)
    for loc in syntactic_children_locs_from(first_loc, core):
        if isinstance(loc.node, (nodes.Return, nodes.Break, nodes.Continue)):
            result.append(loc.node)
    return result
