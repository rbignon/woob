#!/usr/bin/env python3

import ast
from pathlib import Path
import runpy
import sys


class IfExprKiller(ast.NodeVisitor):
    def __init__(self, file):
        self.file = file
        with open(file) as fd:
            self.tree = ast.parse(fd.read(), file)
        self.ok = True

    def check(self):
        self.visit(self.tree)
        return self.ok

    def visit_IfExp(self, node):
        self.ok = False
        print(
            f"{self.file}:{node.lineno}:{node.col_offset}: if-expressions are forbidden",
            file=sys.stderr
        )


mod = runpy.run_path(str(Path(__file__).with_name('checkerlib.py')))

args = mod['parser'].parse_args()

exit_code = 0
for file in mod['files_to_check'](args):
    if not IfExprKiller(file).check():
        exit_code = 1

sys.exit(exit_code)
