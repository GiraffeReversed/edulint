"""
Provides a function to generate and display the control flow graph of a given module.
"""

# adapted from https://github.com/pyta-uoft/pyta/blob/4c858623549e24a49fea7aef9c8ec7c20c836bd6/python_ta/cfg/cfg_generator.py

import argparse
from collections import defaultdict
import importlib.util
import os.path
import sys
from typing import Any, Dict, Optional, Set

import graphviz
from astroid import nodes
from astroid.builder import AstroidBuilder

from edulint.linting.analyses.cfg.graph import CFGBlock, CFGLoc, ControlFlowGraph
from edulint.linting.analyses.cfg.visitor import CFGVisitor
from edulint.linting.analyses.cfg.utils import get_cfg_loc
from edulint.linting.analyses.variable_modification import VarModificationAnalysis
from edulint.linting.analyses.data_dependency import collect_reaching_definitions

GRAPH_OPTIONS = {
    "format": "dot",
    "node_attr": {"shape": "box", "fontname": "Courier New"},
}
SUBGRAPH_OPTIONS = {"fontname": "Courier New"}


def generate_cfg(
    mod: str = "", run_dda: bool = True, visitor_options: Optional[Dict[str, Any]] = None
) -> None:
    """Generate a control flow graph for the given module.

    Supported Options:
      - "separate-condition-blocks": bool
            This option specifies whether the test condition of an if statement gets merged with any
            preceding statements or placed in a new block. By default, it will merge them.
      - "functions": list[str]
            This option specifies whether to restrict the creation of cfgs to just top-level
            function definitions or methods provided in this list. By default, it will create the
            cfg for the entire file.

    Args:
        mod (str): The path to the module. `mod` can either be the path of a file (must have `.py`
            extension) or have no argument (generates a CFG for the Python file from which this
            function is called).
        auto_open (bool): Automatically open the graph in your browser.
        visitor_options (dict): An options dict to configure how the cfgs are generated.
    """
    return _generate(mod=mod, run_dda=run_dda, visitor_options=visitor_options)


def _generate(
    mod: str, run_dda: bool, visitor_options: Optional[Dict[str, Any]]
) -> Dict[nodes.NodeNG, ControlFlowGraph]:
    """Generate a control flow graph for the given module.

    `mod` can either be:
      - the path of a file (must have `.py` extension).
      - no argument -- generate a CFG for the Python file from which this function is called.
    """
    # Generate a control flow graph for the given file
    abs_path = _get_valid_file_path(mod)
    # Print an error message if the file is not valid and early return
    if abs_path is None:  # _get_valid_file_path returns None in case of invalid file
        return

    module = AstroidBuilder().file_build(abs_path)
    visitor = CFGVisitor(options=visitor_options)
    module.accept(visitor)

    if run_dda:
        VarModificationAnalysis().collect(module)
        collect_reaching_definitions(module)

    return visitor.cfgs


def _get_valid_file_path(mod: str = "") -> Optional[str]:
    """Return the valid absolute path of `mod`, a path to the target file."""
    # Allow call to check with empty args
    if mod == "":
        m = sys.modules["__main__"]
        spec = importlib.util.spec_from_file_location(m.__name__, m.__file__)
        mod = spec.origin
    # Enforce the API to only except `mod` type as str
    elif not isinstance(mod, str):
        print(
            "No CFG generated. Input to check, `{}`, has invalid type, must be a string.".format(
                mod
            )
        )
        return

    # At this point, `mod` is of type str
    if not os.path.isfile(mod):
        # `mod` is not a file so print an error message
        print("Could not find the file called, `{}`\n".format(mod))
        return

    # `mod` may be a relative path to a valid file so return its absolute path
    return os.path.abspath(mod)


def _cfg_node_to_id(node: nodes.NodeNG):
    if isinstance(node, nodes.Module):
        return "__main__"
    if isinstance(node, nodes.ClassDef):
        return node.name
    if isinstance(node, nodes.FunctionDef):
        scope_parent = node.scope().parent
        subgraph_label = node.name
        # Update the label to the qualified name if it is a method
        while isinstance(scope_parent, (nodes.FunctionDef, nodes.ClassDef)):
            subgraph_label = scope_parent.name + "." + subgraph_label
            scope_parent = scope_parent.parent.scope()
        return subgraph_label
    print(node)
    assert False, "unreachable"


def generate_dot(
    cfgs: Dict[nodes.NodeNG, ControlFlowGraph], filename: str, generate_dda: bool
) -> None:
    graph = graphviz.Digraph(name=filename, **GRAPH_OPTIONS)
    for node, cfg in cfgs.items():
        with graph.subgraph(name=f"cluster_{cfg.cfg_id}") as c:
            visited = {cfg.start}
            _visit(cfg.start, c, visited, cfg.end, generate_dda)
            for block in cfg.unreachable_blocks:
                _visit(block, c, visited, cfg.end, generate_dda)
            c.attr(label=_cfg_node_to_id(node), **SUBGRAPH_OPTIONS)

    return graph


def display(graph: graphviz.Digraph, filename: str, auto_open: bool = False) -> None:
    graph.render(filename, view=auto_open)


def display_from_block(block: CFGBlock, filename: str, auto_open: bool = False) -> None:
    graph = graphviz.Digraph(name=filename, **GRAPH_OPTIONS)

    with graph.subgraph(name="cluster") as c:
        visited = set()
        _visit(block, c, visited, None)
        c.attr(**SUBGRAPH_OPTIONS)

    graph.render(filename, view=auto_open, cleanup=True)


def _visit(
    block: CFGBlock,
    graph: graphviz.Digraph,
    visited: Set[CFGBlock],
    end: CFGBlock,
    generate_dda: bool,
) -> None:
    """
    Visit a CFGBlock and add it to the control flow graph.
    """

    def _block_to_id(block: CFGBlock) -> str:
        return f"{graph.name}_{block.id}_0"

    def _loc_to_id(loc: CFGLoc) -> str:
        return f"{graph.name}_{loc.block.id}_{loc.pos}"

    def _add_relation(graph, loc, relation_getter, color, scope):
        related_vars = defaultdict(set)
        for var, event in loc.var_events.all():
            for related in relation_getter(event):
                event_loc = get_cfg_loc(related.node)
                if event_loc.node.scope() == scope:
                    related_vars[event_loc].add(related.var.name)
                else:
                    related_vars[get_cfg_loc(event_loc.node.scope())].add(related.var.name)

        for event_loc, vars in related_vars.items():
            if event_loc.node.scope() == scope:
                target = _loc_to_id(event_loc)
            else:
                target = _cfg_node_to_id(event_loc.node.scope())
            graph.edge(
                _loc_to_id(loc),
                target,
                "".join(v + "\n" for v in vars),
                color=color,
                fontcolor=color,
            )

    # Change the fill colour if block is the end of the cfg or is not reachable
    fill_color = "black" if block == end else "grey93" if not block.reachable else "white"

    if len(block.locs) == 0:
        graph.node(_block_to_id(block), label="", fillcolor=fill_color, style="filled")
        last_loc_id = _block_to_id(block)
    else:
        scope = block.locs[0].node.scope()
        for i, loc in enumerate(block.locs):
            graph.node(
                _loc_to_id(loc),
                # Need to escape backslashes explicitly; \l is used for left alignment.
                label=loc.node.as_string().replace("\\", "\\\\").replace("\n", "\\l"),
                fillcolor=fill_color,
                style="filled",
            )
            if i > 0:
                graph.edge(_loc_to_id(loc.block.locs[i - 1]), _loc_to_id(loc))

            _add_relation(graph, loc, lambda event: event.uses, "blue", scope)
            _add_relation(graph, loc, lambda event: event.redefines, "red", scope)
            last_loc_id = _loc_to_id(loc)

    for edge in block.successors:
        if edge.label is not None:
            graph.edge(last_loc_id, _block_to_id(edge.target), str(edge.label))
        else:
            graph.edge(last_loc_id, _block_to_id(edge.target))

        if edge.target not in visited:
            visited.add(edge.target)
            _visit(edge.target, graph, visited, end, generate_dda)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("filename", help="path to file to generate graph for")
    parser.add_argument("-o", "--output", help="name of the file to save the .dot to", default=None)
    parser.add_argument(
        "--dda",
        help="show data from the data dependency analysis",
        action="store_true",
        default=True,
    )
    parser.add_argument(
        "--auto-open",
        help="automatically open the dot after completion",
        action="store_true",
        default=False,
    )
    parser.add_argument("function", help="construct graph only for given funcionts", nargs="*")

    args = parser.parse_args()

    output_filename = args.output if args.output is not None else os.path.basename(args.filename)
    output_filename += ".dot"

    cfgs = generate_cfg(args.filename, run_dda=args.dda)
    if args.function:
        named_cfgs = {_cfg_node_to_id(node): node for node, cfg in cfgs.items()}
        cfgs = {named_cfgs[name]: cfgs[named_cfgs[name]] for name in args.function}
        print(args.function)
    graph = generate_dot(cfgs, output_filename, generate_dda=args.dda)

    display(graph, output_filename, auto_open=args.auto_open)
