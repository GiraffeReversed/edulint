from astroid import nodes  # type: ignore
from typing import TYPE_CHECKING, Optional, Tuple, List, Union, Set, Any, Dict

from pylint.checkers import BaseChecker  # type: ignore
from pylint.checkers.utils import only_required_for_messages

if TYPE_CHECKING:
    from pylint.lint import PyLinter  # type: ignore

from edulint.linting.checkers.utils import (
    is_parents_elif,
    BaseVisitor,
    is_any_assign,
    get_lines_between,
    is_main_block,
    is_block_comment,
    get_statements_count,
    var_defined_before,
    var_used_after,
    eprint,
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


Substitution = Dict[str, Union[nodes.NodeNG, Tuple[str, nodes.NodeNG]]]


class Antiunify:
    def __init__(self):
        self.__num = 0

    def _get_id(self):
        self.__num += 1
        return f"id_{self.__num}"

    def _new_aunifier(self, lt: nodes.NodeNG, rt: nodes.NodeNG, name: str = None):
        id_ = self._get_id()
        name = name if name is not None else lt
        return (name, [id_]), {id_: lt}, {id_: rt}

    def _aunify_consts(self, lt: Any, rt: Any, lt_node: nodes.NodeNG, rt_node: nodes.NodeNG):
        if lt == rt:
            return [], {}, {}
        id_ = self._get_id()
        return [id_], {id_: lt_node}, {id_: rt_node}

    def _aunify_lists(self, lts: List[nodes.NodeNG], rts: List[nodes.NodeNG]):
        assert len(lts) == len(rts)

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
                lt_str, lt_node = lt_child
                rt_str, rt_node = rt_child
                assert (
                    isinstance(lt_str, str)
                    and isinstance(lt_node, nodes.NodeNG)
                    and isinstance(rt_str, str)
                    and isinstance(rt_node, nodes.NodeNG)
                )
                str_core, str_lt_subst, str_rt_subst = self._aunify_consts(
                    lt_str, rt_str, lt_child, rt_child
                )
                node_core, node_lt_subst, node_rt_subst = self.antiunify(lt_node, rt_node)

                core.append(str_core)
                core.append(node_core)
                lt_subst.update(str_lt_subst)
                lt_subst.update(node_lt_subst)
                rt_subst.update(str_rt_subst)
                rt_subst.update(node_rt_subst)

        return core, lt_subst, rt_subst

    def antiunify(
        self, lt: nodes.NodeNG, rt: nodes.NodeNG
    ) -> Tuple[Any, Dict[str, nodes.NodeNG], Dict[str, nodes.NodeNG]]:
        if not isinstance(lt, type(rt)):
            return self._new_aunifier(lt, rt, name=f"{type(lt).__name__}-{type(rt).__name__}")

        aunify_funcname = f"_aunify_{type(lt).__name__.lower()}"
        if hasattr(self, aunify_funcname):
            return getattr(self, aunify_funcname)(lt, rt)

        lt_children = list(lt.get_children())
        rt_children = list(rt.get_children())

        if len(lt_children) != len(rt_children):
            return self._new_aunifier(
                lt,
                rt,
                name=f"{type(lt).__name__}-{len(lt_children)}-{len(rt_children)}",
            )

        core, lt_subst, rt_subst = self._aunify_lists(lt_children, rt_children)
        return (lt, core), lt_subst, rt_subst

    def _aunify_by_attrs(self, attrs: List[str], lt, rt):
        assert isinstance(
            lt, type(rt)
        ), f"lt type: {type(lt).__name__}, rt type: {type(rt).__name__}"

        core = []
        lt_subst = {}
        rt_subst = {}

        for attr in attrs:
            assert hasattr(lt, attr), f"{type(lt).__name__} does not have '{attr}'"
            assert hasattr(rt, attr), f"{type(rt).__name__} does not have '{attr}'"

            lt_attr_val = getattr(lt, attr)
            rt_attr_val = getattr(rt, attr)

            if isinstance(lt_attr_val, list):
                assert isinstance(rt_attr_val, list), f"rt type: {type(rt_attr_val).__name__}"
                if len(lt_attr_val) != len(rt_attr_val):
                    return self._new_aunifier(lt, rt)
                attr_core, attr_lt_subst, attr_rt_subst = self._aunify_lists(
                    lt_attr_val, rt_attr_val
                )
                attr_core = (attr, attr_core)
            elif isinstance(lt_attr_val, nodes.NodeNG):
                attr_core, attr_lt_subst, attr_rt_subst = self.antiunify(lt_attr_val, rt_attr_val)
            else:
                attr_core, attr_lt_subst, attr_rt_subst = self._aunify_consts(
                    lt_attr_val, rt_attr_val, lt, rt
                )

            core.append(attr_core)
            lt_subst.update(attr_lt_subst)
            rt_subst.update(attr_rt_subst)

        return (lt, core), lt_subst, rt_subst

    def _aunify_by_attr(self, attr: str, lt, rt):
        return self._aunify_by_attrs([attr], lt, rt)

    def _aunify_name(self, lt: nodes.Name, rt: nodes.Name):
        return self._aunify_by_attr("name", lt, rt)

    def _aunify_assignname(self, lt: nodes.AssignName, rt: nodes.AssignName):
        return self._aunify_by_attr("name", lt, rt)

    def _aunify_const(self, lt: nodes.Const, rt: nodes.Const):
        return self._aunify_by_attr("value", lt, rt)

    def _aunify_attribute(self, lt: nodes.Attribute, rt: nodes.Attribute):
        return self._aunify_by_attrs(["expr", "attrname"], lt, rt)

    def _aunify_assignattr(self, lt: nodes.AssignAttr, rt: nodes.AssignAttr):
        return self._aunify_by_attrs(["expr", "attrname"], lt, rt)

    def _aunify_compare(self, lt: nodes.Compare, rt: nodes.Compare):
        return self._aunify_by_attrs(["left", "ops"], lt, rt)

    def _aunify_boolop(self, lt: nodes.BoolOp, rt: nodes.BoolOp):
        return self._aunify_by_attrs(["op", "values"], lt, rt)

    def _aunify_binop(self, lt: nodes.BinOp, rt: nodes.BinOp):
        return self._aunify_by_attrs(["left", "op", "right"], lt, rt)

    def _aunify_unaryop(self, lt: nodes.UnaryOp, rt: nodes.UnaryOp):
        return self._aunify_by_attrs(["op", "operand"], lt, rt)

    def _aunify_augassign(self, lt: nodes.AugAssign, rt: nodes.AugAssign):
        return self._aunify_by_attrs(["target", "op", "value"], lt, rt)


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


# def replaceable(node: nodes.NodeNG) -> bool:
# v = isinstance(
#     node,
#     (nodes.Expr, nodes.AssignName, nodes.Name, nodes.Const, nodes.Attribute, nodes.AssignAttr),
# )
# # eprint(node, v)
# return v

TYPES_MATCH_REQUIRED = (nodes.Return,)


def replaceable_with(node1: nodes.NodeNG, node2: nodes.NodeNG) -> bool:
    if isinstance(node1, tuple):
        assert isinstance(node2, tuple)
        op1, n1 = node1
        op2, n2 = node2

        too_different_operators = OPS[op1] == OPS[op2]
        return too_different_operators

    if isinstance(node1, TYPES_MATCH_REQUIRED):
        return isinstance(node2, TYPES_MATCH_REQUIRED)

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


# def count_params_returns(core, s1, s2):
#     def count_returns_in_core(n):
#         if not isinstance(n, tuple):
#             assert not isinstance(n, nodes.NodeNG)
#             return 0

#         tag, children = n
#         return sum(count_returns_in_core(child) for child in children) + int(
#             tag == type(nodes.Return).__name__ and not isinstance(children, tuple)
#         )

#     params_count = 0
#     returns_count = count_returns_in_core

#     for key in s1:
#         n1 = s1[key]
#         n2 = s2[key]


def eprint_list_tree(n: Any, depth: int = 0):
    if isinstance(n, tuple):
        n, children = n
        eprint(depth * " |", f"{type(n).__name__} node" if isinstance(n, nodes.NodeNG) else n)
        for child in children:
            if child:
                eprint_list_tree(child, depth + 1)
    else:
        eprint(depth * " |", n)


def id_with_dash(n: Any) -> bool:
    if isinstance(n, tuple):
        n, children = n
        if isinstance(n, str) and "-" in n:
            return True
        return any(child and id_with_dash(child) for child in children)
    else:
        return False


def is_duplicate_block(lt: nodes.NodeNG, rt: nodes.NodeNG) -> bool:
    core, s1, s2 = Antiunify().antiunify(lt, rt)

    if id_with_dash(core) or not all(replaceable_with(s1[key], s2[key]) for key in s1.keys()):
        return False

    eprint("x")
    eprint(lt.root().file)
    eprint(lt.as_string())
    eprint(rt.as_string())
    eprint()
    eprint_list_tree(core)
    # eprint(s1)
    # eprint(s2)
    # eprint(get_returned_values(lt, rt, core, s1, s2))
    # eprint("\n")
    eprint("x", end="")
    return True


class BigNoDuplicateCode(BaseChecker):  # type: ignore
    name = "big-no-duplicate-code"
    msgs = {
        "R6501": (
            "Lines %i to %i are similar to lines %i through %i.",
            "no-duplicates",
            "Emitted when duplicate code is encountered",
        )
    }

    def __init__(self, linter: "PyLinter"):
        super().__init__(linter)
        # self.to_check = {nodes.FunctionDef: [], nodes.If: [], nodes.While: [], nodes.For: []}
        self.to_check = {}

    def _add_to_check(self, node: nodes.NodeNG) -> None:
        # self.to_check[type(node)].append(node)
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
        self._add_to_check(node)

    def visit_while(self, node: nodes.While) -> None:
        self._add_to_check(node)

    def visit_for(self, node: nodes.For) -> None:
        self._add_to_check(node)

    def visit_functiondef(self, node: nodes.FunctionDef) -> None:
        self._add_to_check(node)

    Interval = Tuple[int, int]
    DuplicateIntervals = Dict[Tuple[Interval, Interval], Tuple[nodes.NodeNG, nodes.NodeNG]]

    @staticmethod
    def _in_interval(i: int, j: int, intervals: DuplicateIntervals) -> bool:
        return any(
            lt_f <= i <= lt_t and rt_f <= j <= rt_t for ((lt_f, lt_t), (rt_f, rt_t)) in intervals
        )

    @staticmethod
    def _remove_interval(lt: nodes.NodeNG, rt: nodes.NodeNG, intervals: DuplicateIntervals) -> None:
        for (lt_f, lt_t), (rt_f, rt_t) in intervals:
            if (
                lt.fromlineno <= lt_f
                and lt_t <= lt.tolineno
                and rt.fromlineno <= rt_f
                and rt_t <= rt.tolineno
            ):
                intervals.pop(((lt_f, lt_t), (rt_f, rt_t)))
                return

    @staticmethod
    def _add_interval(lt: nodes.NodeNG, rt: nodes.NodeNG, intervals: DuplicateIntervals) -> None:
        intervals[((lt.fromlineno, lt.tolineno), (rt.fromlineno, rt.tolineno))] = (lt, rt)

    def close(self) -> None:
        for to_check_in_file in self.to_check.values():
            duplicate_intervals = {}
            for candidate_nodes in to_check_in_file.values():
                for i in range(len(candidate_nodes)):
                    for j in range(i + 1, len(candidate_nodes)):
                        lt = candidate_nodes[i]
                        rt = candidate_nodes[j]
                        if is_duplicate_block(lt, rt) and not BigNoDuplicateCode._in_interval(
                            lt.fromlineno, rt.fromlineno, duplicate_intervals
                        ):
                            BigNoDuplicateCode._remove_interval(lt, rt, duplicate_intervals)
                            BigNoDuplicateCode._add_interval(lt, rt, duplicate_intervals)
                            break

            for lt, rt in duplicate_intervals.values():
                self.add_message(
                    "no-duplicates",
                    node=lt,
                    args=(lt.fromlineno, lt.tolineno, rt.fromlineno, rt.tolineno),
                )


def register(linter: "PyLinter") -> None:
    """This required method auto registers the checker during initialization.
    :param linter: The linter to register the checker to.
    """
    linter.register_checker(NoDuplicateCode(linter))
    linter.register_checker(BigNoDuplicateCode(linter))
