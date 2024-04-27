from astroid import nodes  # type: ignore
from typing import TYPE_CHECKING, Optional, Tuple, List, Union, Set, Any, Dict

from pylint.checkers import BaseChecker  # type: ignore
from pylint.checkers.utils import only_required_for_messages

if TYPE_CHECKING:
    from pylint.lint import PyLinter  # type: ignore

from edulint.linting.analyses.antiunify import antiunify, antiunify_lists, AunifyVar
from edulint.linting.checkers.utils import (
    is_parents_elif,
    BaseVisitor,
    is_any_assign,
    get_lines_between,
    is_main_block,
    is_block_comment,
    get_statements_count,
    var_used_after,
    eprint,
    get_token_count,
    has_else_block,
)


class InvalidExpression(Exception):
    pass


class DuplicateExprVisitor(BaseVisitor[None]):
    EXPR_FUNCTIONS = {
        "abs",
        "max",
        "min",
        "round",
        "sqrt",
        "len",
        "all",
        "any",
        "sum",
        "map",
        "filter",
        "sorted",
        "reversed",
        "int",
        "str",
        "ord",
        "chr",
    }

    def __init__(self) -> None:
        super().__init__()
        self.long_expressions: Dict[str, List[nodes.NodeNG]] = {}

    @classmethod
    def _compute_complexity(cls, node: nodes.NodeNG) -> int:
        fun = cls._compute_complexity

        if isinstance(node, (nodes.Attribute, nodes.Subscript)) and is_any_assign(node.parent):
            raise InvalidExpression

        if isinstance(node, nodes.Call) and node.func.as_string() not in cls.EXPR_FUNCTIONS:
            raise InvalidExpression

        if isinstance(node, nodes.BinOp):
            return 2 + fun(node.left) + fun(node.right)

        if isinstance(node, nodes.BoolOp):
            return len(node.values) - 1 + sum(map(fun, node.values))

        if isinstance(node, nodes.Compare):
            return fun(node.left) + sum(1 + fun(op) for _, op in node.ops)

        if isinstance(node, (nodes.Name, nodes.Const)):
            return 1

        if isinstance(node, nodes.Attribute):
            return 1 + sum(map(fun, node.get_children()))

        return sum(map(fun, node.get_children()))

    def _process_expr(self, node: Optional[nodes.NodeNG]) -> None:
        if node is None:
            return

        try:
            complexity = DuplicateExprVisitor._compute_complexity(node)
        except InvalidExpression:
            self.visit_many(node.get_children())
            return

        if complexity >= 8:  # TODO extract into parameter
            others = self.long_expressions.get(node.as_string(), [])
            others.append(node)
            self.long_expressions[node.as_string()] = others

            self.visit_many(node.get_children())

    def visit_assert(self, node: nodes.Assert) -> None:
        return

    def visit_attribute(self, node: nodes.Attribute) -> None:
        self._process_expr(node)

    def visit_binop(self, node: nodes.BinOp) -> None:
        self._process_expr(node)

    def visit_boolop(self, node: nodes.BoolOp) -> None:
        self._process_expr(node)

    def visit_call(self, node: nodes.Call) -> None:
        self._process_expr(node)

    def visit_compare(self, node: nodes.Compare) -> None:
        self._process_expr(node)

    def visit_dict(self, node: nodes.Dict) -> None:
        self._process_expr(node)

    def visit_dictcomp(self, node: nodes.DictComp) -> None:
        self._process_expr(node)

    def visit_ifexp(self, node: nodes.IfExp) -> None:
        self._process_expr(node)

    def visit_joinedstr(self, node: nodes.JoinedStr) -> None:
        self._process_expr(node)

    def visit_lambda(self, node: nodes.Lambda) -> None:
        self._process_expr(node)

    def visit_list(self, node: nodes.List) -> None:
        self._process_expr(node)

    def visit_listcomp(self, node: nodes.ListComp) -> None:
        self._process_expr(node)

    # def visit_name(self, node: nodes.Name) -> None:
    #     self._process_expr(node)

    def visit_set(self, node: nodes.Set) -> None:
        self._process_expr(node)

    def visit_setcomp(self, node: nodes.SetComp) -> None:
        self._process_expr(node)

    def visit_starred(self, node: nodes.Starred) -> None:
        self._process_expr(node)

    def visit_subscript(self, node: nodes.Subscript) -> None:
        self._process_expr(node)

    def visit_tuple(self, node: nodes.Tuple) -> None:
        self._process_expr(node)

    def visit_unaryop(self, node: nodes.UnaryOp) -> None:
        self._process_expr(node)


class CollectBlocksVisitor(BaseVisitor[None]):
    def __init__(self) -> None:
        self.blocks: List[List[nodes.NodeNG]] = []

    def visit_if(self, node: nodes.If) -> None:
        self.blocks.append(node.body)

        if len(node.orelse) > 0 and not node.has_elif_block():
            self.blocks.append(node.orelse)

        self.visit_many(node.body)
        self.visit_many(node.orelse)

    def visit_loop(self, node: Union[nodes.For, nodes.While]) -> None:
        self.blocks.append(node.body)

        if len(node.orelse) > 0:
            self.blocks.append(node.orelse)

        self.visit_many(node.body)
        self.visit_many(node.orelse)

    def visit_for(self, node: nodes.For) -> None:
        self.visit_loop(node)

    def visit_while(self, node: nodes.While) -> None:
        self.visit_loop(node)

    def visit_with(self, node: nodes.With) -> None:
        self.blocks.append(node.body)
        self.visit_many(node.body)

    def visit_tryexcept(self, node: nodes.TryExcept) -> None:
        self.blocks.append(node.body)

        if len(node.handlers) > 0:
            self.blocks.extend(h.body for h in node.handlers)

        if len(node.orelse) > 0:
            self.blocks.append(node.orelse)

        self.visit_many(node.body)
        self.visit_many([stmt for h in node.handlers for stmt in h.body])
        self.visit_many(node.orelse)

    def visit_functiondef(self, node: nodes.FunctionDef) -> None:
        self.blocks.append(node.body)

        self.visit_many(node.body)

    def visit_module(self, node: nodes.Module) -> None:
        self.blocks.append(
            [
                b
                for b in node.body
                if b
                and not isinstance(b, (nodes.FunctionDef, nodes.ClassDef))
                and not is_main_block(b)
            ]
        )

        self.visit_many(node.body)


class NoDuplicateCode(BaseChecker):  # type: ignore
    name = "no-duplicate-code"
    msgs = {
        "R6502": (
            "Identical code inside all if's branches, move %d lines %s the if.",
            "duplicate-if-branches",
            "Emitted when identical code starts or ends all branches of an if statement.",
        ),
        "R6503": (
            "Identical code inside %d consecutive ifs, join their conditions using 'or'.",
            "duplicate-seq-ifs",
            "Emitted when several consecutive if statements have identical bodies and thus can be "
            "joined by or in their conditions.",
        ),
        "R6504": (
            "A complex expression '%s' used repeatedly (on lines %s). Extract it to a local variable or "
            "create a helper function.",
            "duplicate-exprs",
            "Emitted when an overly complex expression is used multiple times.",
        ),
        "R6505": (
            "Duplicate blocks starting on lines %s. Extract the code to a helper function.",
            "duplicate-blocks",
            "Emitted when there are duplicate blocks of code as a body of an if/elif/else/for/while/with/try-except "
            "block.",
        ),
        "R6506": (
            "Duplicate sequence of %d repetitions of %d lines of code. Use a loop to avoid this.",
            "duplicate-sequence",
            "Emitted when there is a sequence of similar sub-blocks inside a block that can be replaced by a loop.",
        ),
    }

    @only_required_for_messages("duplicate-if-branches", "duplicate-seq-ifs")
    def visit_if(self, node: nodes.If) -> None:
        self.duplicate_if_branches(node)
        self.duplicate_seq_ifs(node)

    def duplicate_if_branches(self, node: nodes.If) -> None:
        def extract_branch_bodies(node: nodes.If) -> Optional[List[nodes.NodeNG]]:
            branches = [node.body]
            current = node
            while current.has_elif_block():
                elif_ = current.orelse[0]
                if not elif_.orelse:
                    return None

                branches.append(elif_.body)
                current = elif_
            branches.append(current.orelse)
            return branches

        def get_stmts_difference(branches: List[nodes.NodeNG], forward: bool) -> int:
            reference = branches[0]
            compare = branches[1:]
            for i in range(min(map(len, branches))):
                for branch in compare:
                    index = i if forward else -i - 1
                    if reference[index].as_string() != branch[index].as_string():
                        return i
            return i + 1

        def add_message(
            branches: List[nodes.NodeNG],
            stmts_difference: int,
            defect_node: nodes.NodeNG,
            forward: bool = True,
        ) -> None:
            reference = branches[0]
            first = reference[0 if forward else -stmts_difference]
            last = reference[stmts_difference - 1 if forward else -1]
            lines_difference = get_lines_between(first, last, including_last=True)

            self.add_message(
                "duplicate-if-branches",
                node=defect_node,
                args=(lines_difference, "before" if forward else "after"),
            )

        if not node.orelse or is_parents_elif(node):
            return

        branches = extract_branch_bodies(node)
        if branches is None:
            return

        same_prefix_len = get_stmts_difference(branches, forward=True)
        if same_prefix_len >= 1:
            add_message(branches, same_prefix_len, node, forward=True)
            if any(same_prefix_len == len(b) for b in branches):
                return

        same_suffix_len = get_stmts_difference(branches, forward=False)
        if same_suffix_len >= 1:
            # allow early returns
            if same_suffix_len == 1 and isinstance(branches[0][-1], nodes.Return):
                i = 0
                while len(branches[i]) == 1:
                    i += 1
                branches = branches[i:]
                if len(branches) < 2:
                    return
            defect_node = branches[0][-1].parent

            # disallow breaking up coherent segments
            same_part = branches[0][-same_suffix_len:]
            if (
                get_statements_count(same_part, include_defs=True, include_name_main=True)
                / (
                    min(
                        get_statements_count(branch, include_defs=True, include_name_main=True)
                        for branch in branches
                    )
                    - same_prefix_len
                )
                < 1 / 2
            ):  # TODO extract into parameter
                return

            add_message(branches, same_suffix_len, defect_node, forward=False)

    def duplicate_seq_ifs(self, node: nodes.If) -> None:
        """
        returns False iff elifs end with else
        """

        def extract_from_elif(node: nodes.If, seq_ifs: List[nodes.NodeNG]) -> bool:
            if len(node.orelse) > 0 and not node.has_elif_block():
                return False

            current = node
            while current.has_elif_block():
                elif_ = current.orelse[0]
                seq_ifs.append(elif_)
                if len(elif_.orelse) > 0 and not elif_.has_elif_block():
                    return False
                current = elif_
            return True

        def extract_from_siblings(node: nodes.If, seq_ifs: List[nodes.NodeNG]) -> None:
            sibling = node.next_sibling()
            while sibling is not None and isinstance(sibling, nodes.If):
                new: List[nodes.NodeNG] = []
                if not extract_from_elif(sibling, new):
                    return
                seq_ifs.append(sibling)
                seq_ifs.extend(new)
                sibling = sibling.next_sibling()

        def same_ifs_count(seq_ifs: List[nodes.NodeNG], start: int) -> int:
            reference = seq_ifs[start].body
            for i in range(start + 1, len(seq_ifs)):
                # do not suggest join of elif and sibling
                if seq_ifs[start].parent not in seq_ifs[i].node_ancestors():
                    return i - start

                compared = seq_ifs[i].body
                if len(reference) != len(compared):
                    return i - start
                for j in range(len(reference)):
                    if reference[j].as_string() != compared[j].as_string():
                        return i - start
            return len(seq_ifs) - start

        prev_sibling = node.previous_sibling()
        if is_parents_elif(node) or (
            isinstance(prev_sibling, nodes.If) and extract_from_elif(prev_sibling, [])
        ):
            return

        seq_ifs = [node]

        if not extract_from_elif(node, seq_ifs):
            return
        extract_from_siblings(node, seq_ifs)

        if len(seq_ifs) == 1:
            return

        i = 0
        while i < len(seq_ifs) - 1:
            count = same_ifs_count(seq_ifs, i)
            if count > 1:
                first = seq_ifs[i]
                assert isinstance(seq_ifs[i + count - 1], nodes.If)
                last = seq_ifs[i + count - 1].body[-1]

                self.add_message(
                    "duplicate-seq-ifs",
                    line=first.fromlineno,
                    col_offset=first.col_offset,
                    end_lineno=last.tolineno,
                    end_col_offset=last.end_col_offset,
                    args=(count,),
                )
            i += count

    def duplicate_exprs(self, node: nodes.Module) -> None:
        visitor = DuplicateExprVisitor()
        visitor.visit(node)

        emitted = set()

        for name, exprs in sorted(
            visitor.long_expressions.items(), key=lambda pair: -len(pair[0][0])
        ):
            if len(exprs) >= 2:
                if exprs[0].parent not in emitted:
                    expr_lines = [
                        str(expr.fromlineno)
                        for expr in sorted(exprs, key=lambda e: (e.fromlineno, e.tolineno))
                    ]
                    self.add_message(
                        "duplicate-exprs", node=exprs[0], args=(name, ", ".join(expr_lines))
                    )
                emitted.update(exprs)

    def duplicate_blocks(self, node: nodes.Module) -> None:
        def update_diffs(
            stmt1: nodes.NodeNG, stmt2: nodes.NodeNG, current_diffs: Set[Tuple[str, str]]
        ) -> bool:
            if isinstance(stmt1, nodes.Compare):
                for (op1, _), (op2, _) in zip(stmt1.ops, stmt2.ops):
                    if op1 != op2:
                        current_diffs.add((op1, op2))
            elif isinstance(stmt1, nodes.BinOp) and stmt1.op != stmt2.op:
                current_diffs.add((stmt1.op, stmt2.op))
            elif isinstance(stmt1, nodes.BoolOp) and stmt1.op != stmt2.op:
                return False
            elif isinstance(stmt1, nodes.Name) and stmt1.name != stmt2.name:
                current_diffs.add((stmt1.name, stmt2.name))
            elif isinstance(stmt1, nodes.Const) and stmt1.value != stmt2.value:
                current_diffs.add((str(stmt1.value), str(stmt2.value)))
            elif isinstance(stmt1, nodes.Attribute) and stmt1.attrname != stmt2.attrname:
                current_diffs.add((stmt1.attrname, stmt2.attrname))
            elif isinstance(stmt1, nodes.UnaryOp) and stmt1.op != stmt2.op:
                current_diffs.add((stmt1.op, stmt2.op))
            return True

        def duplicate_blocks(
            block1: List[nodes.NodeNG],
            block2: List[nodes.NodeNG],
            max_diff: int,
            current_diffs: Set[Tuple[str, str]],
        ) -> bool:
            if len(block1) != len(block2):
                return False
            for stmt1, stmt2 in zip(block1, block2):
                if not isinstance(stmt1, type(stmt2)):
                    return False

                children1 = list(stmt1.get_children())
                children2 = list(stmt2.get_children())

                if len(children1) != len(children2):
                    return False

                if not update_diffs(stmt1, stmt2, current_diffs) or len(current_diffs) > max_diff:
                    return False

                if not duplicate_blocks(children1, children2, max_diff, current_diffs):
                    return False
            return True

        MIN_LINES = 3
        MAX_DIFF = 3

        visitor = CollectBlocksVisitor()
        visitor.visit(node)

        blocks = [
            block
            for block in visitor.blocks
            if len(block) > 0
            and get_lines_between(block[0], block[-1], including_last=True) >= MIN_LINES
        ]

        if len(blocks) < 2:
            return

        blocks.sort(key=lambda block: (block[0].fromlineno, block[-1].tolineno))
        max_closed_line = 0

        for i in range(len(blocks)):
            for j in range(i + 1, len(blocks)):
                block1 = blocks[i]
                block2 = blocks[j]

                if (
                    not isinstance(block1[0].parent, type(block2[0].parent))
                    or block1[-1].tolineno <= max_closed_line
                ):
                    continue

                if duplicate_blocks(block1, block2, MAX_DIFF, set()):
                    self.add_message(
                        "duplicate-blocks",
                        line=block1[0].fromlineno,
                        col_offset=block1[0].col_offset,
                        end_lineno=block1[-1].tolineno,
                        end_col_offset=block1[-1].end_col_offset,
                        args=(f"{block1[0].fromlineno} and {block2[0].fromlineno}",),
                    )
                    max_closed_line = block1[-1].tolineno
                    break

    def duplicate_sequence(self, node: nodes.Module) -> None:
        def can_use_range(diffs: List[Any]) -> bool:
            if all(e is None for e in diffs):
                return True
            if not all(isinstance(e, int) for e in diffs):
                return False

            assert len(diffs) >= 2
            step = diffs[1] - diffs[0]
            return all(e1 + step == e2 for e1, e2 in zip(diffs, diffs[1:]))

        def get_single_diff_list(
            stmts1: List[nodes.NodeNG], stmts2: List[nodes.NodeNG]
        ) -> Optional[Tuple[Tuple[Any, Any], List[int]]]:
            if len(stmts1) != len(stmts2):
                return None

            result = None
            for i, (stmt1, stmt2) in enumerate(zip(stmts1, stmts2)):
                subresult = get_single_diff(stmt1, stmt2)
                if subresult is None or (result is not None and result[0] != subresult[0]):
                    return None

                diff, path = subresult
                if diff != (None, None):
                    path.append(i)
                    result = diff, path

            if result is None:
                return (None, None), []
            return result

        def get_single_diff(
            stmt1: nodes.NodeNG, stmt2: nodes.NodeNG
        ) -> Optional[Tuple[Tuple[Any, Any], List[int]]]:
            if not isinstance(stmt1, type(stmt2)):
                return None
            if isinstance(stmt1, nodes.Const):
                if not isinstance(stmt1.value, type(stmt2.value)):
                    return None
                if stmt1.value == stmt2.value:
                    return (None, None), []
                return (stmt1.value, stmt2.value), []
            if isinstance(stmt1, nodes.Name) and stmt1.name != stmt2.name:
                return None
            if isinstance(stmt1, nodes.Attribute) and stmt1.attrname != stmt2.attrname:
                return None
            if (
                isinstance(stmt1, (nodes.BinOp, nodes.BoolOp, nodes.UnaryOp))
                and stmt1.op != stmt2.op
            ):
                return None
            if isinstance(stmt1, nodes.Compare) and any(
                o1 != o2 for (o1, _), (o2, _) in zip(stmt1.ops, stmt2.ops)
            ):
                return None
            if isinstance(stmt1, nodes.Assign) and any(
                t1.as_string() != t2.as_string() for t1, t2 in zip(stmt1.targets, stmt2.targets)
            ):
                return None
            if (
                isinstance(stmt1, (nodes.AugAssign, nodes.AnnAssign))
                and stmt1.target.as_string() != stmt2.target.as_string()
            ):
                return None
            if is_block_comment(stmt1):
                return None
            if isinstance(stmt1, (nodes.Assert, nodes.Import, nodes.ImportFrom)):
                return None
            if (
                isinstance(stmt1, nodes.Call)
                and isinstance(stmt1.func, nodes.Name)
                and stmt1.func.name == "print"
            ):
                return None

            return get_single_diff_list(list(stmt1.get_children()), list(stmt2.get_children()))

        def get_seq_diffs(block: List[nodes.NodeNG], subblock_len: int, start: int) -> List[Any]:
            path = None
            diffs: List[Any] = []
            for i in range(start, len(block) - subblock_len, subblock_len):
                subblock1 = block[i : i + subblock_len]
                subblock2 = block[i + subblock_len : i + 2 * subblock_len]

                subresult = get_single_diff_list(subblock1, subblock2)
                if subresult is None:
                    return diffs

                diff, subpath = subresult
                if path is not None and len(path) > 0 and len(subpath) > 0 and path != subpath:
                    return diffs
                if (
                    path is not None
                    and len(path) == 0
                    and len(subpath) > 0
                    and len(diffs) >= DUPL_SEQ_LEN
                ):
                    return diffs
                if path is None or (len(path) == 0 and len(subpath) > 0):
                    path = subpath

                if len(diffs) == 0:
                    diffs.extend(diff)
                else:
                    diffs.append(diff[1])

            return diffs

        def process_block(self: "NoDuplicateCode", block: List[nodes.NodeNG]) -> None:
            max_subblock_len = len(block) // DUPL_SEQ_LEN

            if max_subblock_len == 0:
                return

            start = 0
            while start < len(block) - 1:
                for subblock_len in range(1, max_subblock_len + 1):
                    diffs = get_seq_diffs(block, subblock_len, start)
                    if (len(diffs) >= DUPL_SEQ_LEN and can_use_range(diffs)) or len(
                        diffs
                    ) >= DUPL_SEQ_LEN_NO_RANGE:
                        first_subblock = block[start : start + subblock_len]
                        last_subblock = block[
                            start
                            + (len(diffs) - 1) * subblock_len : start
                            + len(diffs) * subblock_len
                        ]
                        self.add_message(
                            "duplicate-sequence",
                            line=first_subblock[0].fromlineno,
                            col_offset=first_subblock[0].col_offset,
                            end_lineno=last_subblock[-1].tolineno,
                            end_col_offset=last_subblock[-1].end_col_offset,
                            args=(
                                len(diffs),
                                get_lines_between(
                                    first_subblock[0], first_subblock[-1], including_last=True
                                ),
                            ),
                        )
                        start += len(diffs) * subblock_len
                        break
                else:
                    start += 1

        DUPL_SEQ_LEN = 4
        DUPL_SEQ_LEN_NO_RANGE = 5

        visitor = CollectBlocksVisitor()
        visitor.visit(node)

        blocks = [block for block in visitor.blocks if len(block) > 0]
        blocks.sort(key=lambda block: (block[0].fromlineno, block[-1].tolineno))

        for block in blocks:
            if len(block) >= 2:
                process_block(self, block)

    @only_required_for_messages("duplicate-exprs", "duplicate-blocks", "duplicate-sequence")
    def visit_module(self, node: nodes.Module) -> None:
        self.duplicate_exprs(node)
        self.duplicate_blocks(node)
        self.duplicate_sequence(node)


OPS = {
    "+": 0,
    "+=": 0,
    "-": 0,
    "-=": 0,
    "*": 1,
    "*=": 1,
    "/": 2,
    "/=": 2,
    "//": 2,
    "//=": 2,
    "%": 3,
    "%=": 3,
    "**": 4,
    "**=": 4,
    "==": 5,
    "!=": 5,
    ">": 6,
    "<": 6,
    ">=": 6,
    "<=": 6,
    "and": 7,
    "or": 7,
    "not": 8,
    "is": 9,
    "is not": 9,
    "in": 15,
    "not in": 15,
    "&": 10,
    "&=": 10,
    "|": 10,
    "|=": 10,
    "^": 11,
    "^-": 11,
    "~": 12,
    "~=": 12,
    "<<": 13,
    "<<=": 13,
    ">>": 14,
    ">>=": 14,
}

TYPES_MATCH_REQUIRED = (nodes.Return,)


def replaceable_with(v1, v2) -> bool:
    if isinstance(v1, str) and v1 in OPS and isinstance(v2, str) and v2 in OPS:
        too_different_operators = OPS[v1] == OPS[v2]
        return too_different_operators

    if isinstance(v1, TYPES_MATCH_REQUIRED):
        return isinstance(v2, TYPES_MATCH_REQUIRED)

    return True


def get_returned_values(lt, rt, core, s1, s2):
    returned_values = set()

    def find_returned_values(nx):
        if not isinstance(nx, tuple):
            assert not isinstance(nx, nodes.NodeNG)
            return

        n, children = nx
        # eprint(n, children)
        if isinstance(n, nodes.Return):
            assert len(children) <= 1
            if len(children) == 0:
                returned_values.add("None")
            elif isinstance(children[0], tuple):
                assert isinstance(children[0][0], nodes.NodeNG)
                returned_values.add(children[0][0].as_string())
            else:
                raise Exception()

        if isinstance(n, nodes.AssignName):
            if len(children) == 0 and var_used_after(lt, n):
                returned_values.add(n.name)
            elif len(children) == 1:
                # eprint(children[0])
                if var_used_after(lt, s1[children[0][0]]) or var_used_after(rt, s2[children[0][0]]):
                    returned_values.add(f"{s1[children[0][0]].name}-{s2[children[0][0]].name}")

        for child in children:
            if child:
                find_returned_values(child)

    try:
        find_returned_values(core)
    except Exception as e:
        eprint(e)
        return None
    # find_returned_values(core)
    return returned_values


def similar_to_function(lt: nodes.NodeNG, rt: nodes.NodeNG, core, s1, s2) -> bool:
    if length_or_type_mismatch([s1, s2]) or not all(
        replaceable_with(s1[key], s2[key]) for key in s1.keys()
    ):
        return False

    size_before_decomposition = get_statements_count(
        lt, include_defs=False, include_name_main=True
    ) + get_statements_count(rt, include_defs=False, include_name_main=True)
    size_after_decomposition = (
        # function header
        1
        # implementation
        + get_statements_count(core, include_defs=False, include_name_main=True)
        + 1  # return
        # calls
        + 2
    )

    return size_after_decomposition < size_before_decomposition


def length_or_type_mismatch(subs) -> bool:
    return any("-" in id_.name for id_ in subs[0])


def assignment_to_aunify_var(node) -> bool:
    if isinstance(node, nodes.AssignName) and isinstance(node.name, AunifyVar):
        return True

    if isinstance(node, list):
        return any(assignment_to_aunify_var(n) for n in node)

    return any(assignment_to_aunify_var(n) for n in node.get_children())


def called_aunify_var(node, inside_called: bool = False) -> bool:
    if inside_called and (
        (isinstance(node, nodes.Name) and isinstance(node.name, AunifyVar))
        or (isinstance(node, nodes.Attribute) and isinstance(node.attrname, AunifyVar))
    ):
        return True

    if isinstance(node, nodes.Call):
        if called_aunify_var(node.func, inside_called=True):
            return True
        return any(called_aunify_var(n) for n in node.get_children())

    if isinstance(node, nodes.BinOp) and isinstance(node.op, AunifyVar):
        return True

    if isinstance(node, nodes.Compare) and any(isinstance(op, AunifyVar) for op in node.ops):
        return True

    if isinstance(node, list):
        return any(called_aunify_var(n) for n in node)

    return any(called_aunify_var(n) for n in node.get_children())


def extract_from_elif(node: nodes.If, result: List[nodes.If] = None) -> bool:
    """
    returns True iff elifs end with else
    """

    def count_elses(node: nodes.If) -> int:
        if len(node.body) != 1 or not isinstance(node.body[0], nodes.If):
            return 0

        node = node.body[0]
        result = 0
        while node.has_elif_block():
            node = node.orelse[0]
            result += 1
        return result + (1 if has_else_block(node) else 0)

    result = [node] if result is None else result
    if has_else_block(node):
        return True, result

    current = node
    else_count = count_elses(node)
    while current.has_elif_block():
        elif_ = current.orelse[0]
        result.append(elif_)
        if has_else_block(elif_):
            return True, (
                result if else_count == 0 or else_count >= len(result) else result[:-else_count]
            )
        current = elif_
    return False, result


def extract_from_siblings(node: nodes.If, seq_ifs: List[nodes.NodeNG]) -> None:
    sibling = node.next_sibling()
    while sibling is not None and isinstance(sibling, nodes.If):
        new: List[nodes.NodeNG] = []
        if not extract_from_elif(sibling, new):
            return
        seq_ifs.append(sibling)
        seq_ifs.extend(new)
        sibling = sibling.next_sibling()


def if_to_variables(self, node: nodes.If) -> bool:

    def get_bodies(ifs: List[nodes.If]) -> List[List[nodes.NodeNG]]:
        result = []
        for i, if_ in enumerate(ifs):
            result.append(if_.body)
            if i == len(ifs) - 1:
                result.append(if_.orelse)
        return result

    def get_core(if_bodies: List[List[nodes.NodeNG]]):
        core, sl, sr = antiunify_lists(if_bodies[0], if_bodies[1])
        subs = [sl, sr]
        for i in range(2, len(if_bodies)):
            core, sl, sr = antiunify_lists(core, if_bodies[i])

            for sub in subs:
                sub.update(sl)
            subs.append(sr)

        return core, subs

    if is_parents_elif(node):
        return False

    ends_with_else, ifs = extract_from_elif(node)
    if not ends_with_else:
        return False

    if_bodies = get_bodies(ifs)
    assert len(if_bodies) >= 2
    core, subs = get_core(if_bodies)

    if length_or_type_mismatch(subs) or assignment_to_aunify_var(core) or called_aunify_var(core):
        return False

    tokens_before = get_token_count(node)
    stmts_before = get_statements_count(node, include_defs=False, include_name_main=True)

    core_tokens = get_token_count(core)
    test_tokens = sum(get_token_count(if_.test) for if_ in ifs)
    core_stmts = get_statements_count(core, include_defs=False, include_name_main=True)

    vars_needed = len(subs[0])  # TODO may be lower

    tokens_after = (
        core_tokens
        + (test_tokens + len(if_bodies))  # if test ... else
        + len(if_bodies) * vars_needed * 3  # var = val
    )
    stmts_after = core_stmts + (len(if_bodies)) * (vars_needed + 1)  # + tests
    suggest_ternary = False

    # TODO count tokens in values
    if len(if_bodies) == 2 and self.linter.is_message_enabled("if-to-ternary"):
        tokens_after_ternary = core_tokens + vars_needed * (
            test_tokens + 4  # v1 if test else v2
        )

        if tokens_after_ternary < tokens_after:
            tokens_after = tokens_after_ternary
            stmts_after = core_stmts
            suggest_ternary = True

    if not (
        tokens_after < 0.75 * tokens_before  # TODO extract into variable
        and stmts_after <= stmts_before
    ):
        return False

    if suggest_ternary:
        self.add_message("if-to-ternary", node=node)
    else:
        self.add_message("if-to-variables", node=node)


def if_into_similar(lt: nodes.If, rt: nodes.If, core, s1, s2) -> bool:

    if (
        not isinstance(lt.parent, nodes.If)
        or lt.parent != rt.parent
        or len(lt.parent.body) != 1
        or lt.parent.body[0] != lt
        or len(rt.parent.body) != 1
        or rt.parent.orelse[0] != rt
    ):
        return False

    if length_or_type_mismatch([s1, s2]):
        return False

    if len(set(s1.values()) | set(s2.values())) != 2:
        return False

    size_before_decomposition = get_token_count(lt.parent)
    size_after_decomposition = get_token_count(core) + len(s1) * (
        4 + get_token_count(lt.parent.test)  # V1 if ... else V2
    )

    return size_after_decomposition < size_before_decomposition


class BigNoDuplicateCode(BaseChecker):  # type: ignore
    name = "big-no-duplicate-code"
    msgs = {
        "R6801": (
            "Lines %i to %i are similar to lines %i through %i. Extract them to a common function.",
            "similar-to-function",
            "",
        ),
        "R6802": (
            "Extract code into loop",
            "similar-to-loop",
            "",
        ),
        "R6803": (
            "Use existing function",
            "similar-to-call",
            "",
        ),
        "R6804": (
            "Extract ifs to ternary",
            "if-to-ternary",
            "",
        ),
        "R6805": (
            "Combine",
            "seq-into-similar",
            "",
        ),
        "R6806": (
            "Extract ifs",
            "if-to-variables",
            "",
        ),
        "R6851": (
            "Identical code inside all if's branches, move %d lines %s the if.",
            "identical-before-after-branch",
            "Emitted when identical code starts or ends all branches of an if statement.",
        ),
        "R6852": (
            "Identical code inside %d consecutive ifs, join their conditions using 'or'.",
            "identical-seq-ifs",
            "Emitted when several consecutive if statements have identical bodies and thus can be "
            "joined by or in their conditions.",
        ),
        "R6853": (
            "A complex expression '%s' used repeatedly (on lines %s). Extract it to a local variable.",
            "identical-exprs-to-variable",
            "Emitted when an overly complex expression is used multiple times.",
        ),
        "R6854": (
            "A complex expression '%s' used repeatedly (on lines %s). Extract it to a local variable.",
            "identical-exprs-to-function",
            "Emitted when an overly complex expression is used multiple times.",
        ),
    }

    def __init__(self, linter: "PyLinter"):
        super().__init__(linter)
        self.to_check = {}

    def _add_to_check(self, node: nodes.NodeNG) -> None:
        fn = node.root().name
        if fn not in self.to_check:
            self.to_check[fn] = {
                nodes.FunctionDef: [],
                nodes.If: [],
                nodes.While: [],
                nodes.For: [],
            }
        self.to_check[fn][type(node)].append(node)

    def visit_if(self, node: nodes.If) -> None:
        any_message1 = self.identical_before_after_branch(node)
        any_message2 = self.identical_seq_ifs(node)

        if not any_message1 and not any_message2:
            self._add_to_check(node)

    def visit_while(self, node: nodes.While) -> None:
        self._add_to_check(node)

    def visit_for(self, node: nodes.For) -> None:
        self._add_to_check(node)

    def visit_functiondef(self, node: nodes.FunctionDef) -> None:
        self._add_to_check(node)

    def identical_before_after_branch(self, node: nodes.If) -> bool:
        def extract_branch_bodies(node: nodes.If) -> Optional[List[nodes.NodeNG]]:
            branches = [node.body]
            current = node
            while current.has_elif_block():
                elif_ = current.orelse[0]
                if not elif_.orelse:
                    return None

                branches.append(elif_.body)
                current = elif_
            branches.append(current.orelse)
            return branches

        def get_stmts_difference(branches: List[nodes.NodeNG], forward: bool) -> int:
            reference = branches[0]
            compare = branches[1:]
            for i in range(min(map(len, branches))):
                for branch in compare:
                    index = i if forward else -i - 1
                    if reference[index].as_string() != branch[index].as_string():
                        return i
            return i + 1

        def add_message(
            branches: List[nodes.NodeNG],
            stmts_difference: int,
            defect_node: nodes.NodeNG,
            forward: bool = True,
        ) -> None:
            reference = branches[0]
            first = reference[0 if forward else -stmts_difference]
            last = reference[stmts_difference - 1 if forward else -1]
            lines_difference = get_lines_between(first, last, including_last=True)

            self.add_message(
                "identical-before-after-branch",
                node=defect_node,
                args=(lines_difference, "before" if forward else "after"),
            )

        if not node.orelse or is_parents_elif(node):
            return False

        branches = extract_branch_bodies(node)
        if branches is None:
            return False

        any_message = False
        same_prefix_len = get_stmts_difference(branches, forward=True)
        if same_prefix_len >= 1:
            add_message(branches, same_prefix_len, node, forward=True)
            any_message = True
            if any(same_prefix_len == len(b) for b in branches):
                return any_message

        same_suffix_len = get_stmts_difference(branches, forward=False)
        if same_suffix_len >= 1:
            # allow early returns
            if same_suffix_len == 1 and isinstance(branches[0][-1], nodes.Return):
                i = 0
                while len(branches[i]) == 1:
                    i += 1
                branches = branches[i:]
                if len(branches) < 2:
                    return any_message
            defect_node = branches[0][-1].parent

            # disallow breaking up coherent segments
            same_part = branches[0][-same_suffix_len:]
            if (
                get_statements_count(same_part, include_defs=True, include_name_main=True)
                / (
                    min(
                        get_statements_count(branch, include_defs=True, include_name_main=True)
                        for branch in branches
                    )
                    - same_prefix_len
                )
                < 1 / 2
            ):  # TODO extract into parameter
                return any_message

            add_message(branches, same_suffix_len, defect_node, forward=False)
            any_message = True
        return any_message

    def identical_seq_ifs(self, node: nodes.If) -> bool:

        def same_ifs_count(seq_ifs: List[nodes.NodeNG], start: int) -> int:
            reference = seq_ifs[start].body
            for i in range(start + 1, len(seq_ifs)):
                # do not suggest join of elif and sibling
                if seq_ifs[start].parent not in seq_ifs[i].node_ancestors():
                    return i - start

                compared = seq_ifs[i].body
                if len(reference) != len(compared):
                    return i - start
                for j in range(len(reference)):
                    if reference[j].as_string() != compared[j].as_string():
                        return i - start
            return len(seq_ifs) - start

        prev_sibling = node.previous_sibling()
        if is_parents_elif(node) or (
            isinstance(prev_sibling, nodes.If) and not extract_from_elif(prev_sibling)[0]
        ):
            return False

        ends_with_else, seq_ifs = extract_from_elif(node)
        if ends_with_else:
            return False
        extract_from_siblings(node, seq_ifs)

        if len(seq_ifs) == 1:
            return False

        i = 0
        any_message = False
        while i < len(seq_ifs) - 1:
            count = same_ifs_count(seq_ifs, i)
            if count > 1:
                first = seq_ifs[i]
                assert isinstance(seq_ifs[i + count - 1], nodes.If)
                last = seq_ifs[i + count - 1].body[-1]

                self.add_message(
                    "identical-seq-ifs",
                    line=first.fromlineno,
                    col_offset=first.col_offset,
                    end_lineno=last.tolineno,
                    end_col_offset=last.end_col_offset,
                    args=(count,),
                )
                any_message = True
            i += count
        return any_message

    def close(self) -> None:
        def candidate_lt():
            for to_check_in_file in self.to_check.values():
                for to_check_of_type in to_check_in_file.values():
                    to_check_of_type.sort(key=lambda v: (v.fromlineno, v.col_offset))
                nodes = sorted(
                    [v for to_check_of_type in to_check_in_file.values() for v in to_check_of_type],
                    key=lambda v: (v.fromlineno, v.col_offset),
                )
                for node in nodes:
                    yield to_check_in_file, node

        def candidate_rt(to_check_in_file, lt):
            for rt in to_check_in_file[type(lt)]:
                if lt.fromlineno < rt.fromlineno:
                    yield rt

        for to_check_in_file, lt in candidate_lt():
            if isinstance(lt, nodes.If) and if_to_variables(self, lt):
                continue

            for rt in candidate_rt(to_check_in_file, lt):
                core, s1, s2 = antiunify(lt, rt)
                if similar_to_function(lt, rt, core, s1, s2):
                    self.add_message("similar-to-function", node=lt)
                    break

    # Interval = Tuple[int, int]
    # DuplicateIntervals = Dict[Tuple[Interval, Interval], Tuple[nodes.NodeNG, nodes.NodeNG]]

    # @staticmethod
    # def _in_interval(i: int, j: int, intervals: DuplicateIntervals) -> bool:
    #     return any(
    #         lt_f <= i <= lt_t and rt_f <= j <= rt_t for ((lt_f, lt_t), (rt_f, rt_t)) in intervals
    #     )

    # @staticmethod
    # def _remove_interval(lt: nodes.NodeNG, rt: nodes.NodeNG, intervals: DuplicateIntervals) -> None:
    #     for (lt_f, lt_t), (rt_f, rt_t) in intervals:
    #         if (
    #             lt.fromlineno <= lt_f
    #             and lt_t <= lt.tolineno
    #             and rt.fromlineno <= rt_f
    #             and rt_t <= rt.tolineno
    #         ):
    #             intervals.pop(((lt_f, lt_t), (rt_f, rt_t)))
    #             return

    # @staticmethod
    # def _add_interval(lt: nodes.NodeNG, rt: nodes.NodeNG, intervals: DuplicateIntervals) -> None:
    #     intervals[((lt.fromlineno, lt.tolineno), (rt.fromlineno, rt.tolineno))] = (lt, rt)

    # def close(self) -> None:
    #     for fn, to_check_in_file in self.to_check.items():
    #         duplicate_intervals = {}
    #         for candidate_nodes in to_check_in_file.values():
    #             for i in range(len(candidate_nodes)):
    #                 for j in range(i + 1, len(candidate_nodes)):
    #                     lt = candidate_nodes[i]
    #                     rt = candidate_nodes[j]
    #                     if is_duplicate_block(lt, rt) and not BigNoDuplicateCode._in_interval(
    #                         lt.fromlineno, rt.fromlineno, duplicate_intervals
    #                     ):
    #                         BigNoDuplicateCode._remove_interval(lt, rt, duplicate_intervals)
    #                         BigNoDuplicateCode._add_interval(lt, rt, duplicate_intervals)
    #                         break

    #         for lt, rt in duplicate_intervals.values():
    #             self.add_message(
    #                 "no-duplicates",
    #                 node=lt,
    #                 args=(lt.fromlineno, lt.tolineno, rt.fromlineno, rt.tolineno),
    #             )


def register(linter: "PyLinter") -> None:
    """This required method auto registers the checker during initialization.
    :param linter: The linter to register the checker to.
    """
    linter.register_checker(NoDuplicateCode(linter))
    linter.register_checker(BigNoDuplicateCode(linter))
