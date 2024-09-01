"""Patch to add transforms for creating control flow graphs.
"""

# adapted from https://github.com/pyta-uoft/pyta/blob/4c858623549e24a49fea7aef9c8ec7c20c836bd6/python_ta/patches/transforms.py

import astroid
from pylint.lint import PyLinter

from edulint.linting.analyses.variable_scope import UnknowableLocalsException
from edulint.linting.analyses.variable_modification import VarModificationAnalysis
from edulint.linting.analyses.data_dependency import collect_reaching_definitions

from edulint.linting.analyses.antiunify import AunifyVar
from edulint.linting.analyses.cfg.visitor import CFGVisitor
from loguru import logger


def patch_ast_transforms():
    old_get_ast = PyLinter.get_ast

    def new_get_ast(self, filepath, modname, data=None):
        ast = old_get_ast(self, filepath, modname, data)
        if ast is not None:
            ast.accept(CFGVisitor())
            if len(ast.cfg_loc.block.locs) == 0:
                ast.cfg_loc.var_events.successful = False
            else:
                try:
                    VarModificationAnalysis().collect(ast)
                    collect_reaching_definitions(ast)
                    ast.cfg_loc.var_events.successful = True
                except UnknowableLocalsException as e:
                    ast.cfg_loc.var_events.successful = False
                    logger.warning(str(e))
        return ast

    PyLinter.get_ast = new_get_ast
    astroid.raw_building._CONST_PROXY[AunifyVar] = None


def register(_linter: "PyLinter") -> None:
    """This required method auto registers the checker during initialization.
    :param linter: The linter to register the checker to.
    """
    patch_ast_transforms()
