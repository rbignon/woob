#!/usr/bin/env python3

import ast
from pathlib import Path
import runpy
import sys


mod = runpy.run_path(str(Path(__file__).with_name('checkerlib.py')))
Checker = mod['Checker']


class IfExprKiller(Checker, ast.NodeVisitor):
    def __init__(self, filename):
        super().__init__(filename)
        self.parse_ast()

    def check(self):
        self.visit(self.tree)
        return self.ok

    def visit_IfExp(self, node):
        self.add_error(
            "if-expressions are forbidden",
            line=node.lineno, col=node.col_offset,
        )


args = mod['parser'].parse_args()

exit_code = 0
for file in mod['files_to_check'](args):
    checker = IfExprKiller(file)
    checker.parse_noqa()
    if not checker.check():
        exit_code = 1

sys.exit(exit_code)
