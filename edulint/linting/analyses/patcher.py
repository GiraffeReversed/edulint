"""Patch to add transforms for creating control flow graphs.
"""

# adapted from https://github.com/pyta-uoft/pyta/blob/4c858623549e24a49fea7aef9c8ec7c20c836bd6/python_ta/patches/transforms.py

from pylint.lint import PyLinter

from edulint.linting.analyses.cfg.visitor import CFGVisitor


def patch_ast_transforms():
    old_get_ast = PyLinter.get_ast

    def new_get_ast(self, filepath, modname, data):
        ast = old_get_ast(self, filepath, modname, data)
        if ast is not None:
            try:
                ast.accept(CFGVisitor())
            except Exception:
                pass
        return ast

    PyLinter.get_ast = new_get_ast


def register(_linter: "PyLinter") -> None:
    """This required method auto registers the checker during initialization.
    :param linter: The linter to register the checker to.
    """
    patch_ast_transforms()
