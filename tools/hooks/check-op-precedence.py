#!/usr/bin/env python3

import ast
from pathlib import Path
import runpy
import sys
import tokenize

from asttokens import ASTTokens


mod = runpy.run_path(str(Path(__file__).with_name('checkerlib.py')))
Checker = mod['Checker']


bit_ops = (ast.BitOr, ast.BitAnd, ast.BitXor, ast.LShift, ast.RShift)
math_ops = (ast.Add, ast.Sub, ast.Mult, ast.MatMult, ast.Div, ast.FloorDiv, ast.Mod)

dubious_ops = [
    bit_ops,
]

dubious_ops_groups = [
    (bit_ops, math_ops),
]


class OpPrioVerifier(Checker, ast.NodeVisitor):
    def __init__(self, filename):
        super().__init__(filename)
        with open(self.filename) as fd:
            self.astt = ASTTokens(fd.read(), parse=True)
        self.tree = self.astt.tree
        self.tokens = self.astt.tokens

    def has_paren(self, tokens, expected_paren):
        for token in tokens:
            if token.type in (tokenize.NL, tokenize.COMMENT):
                continue
            elif token.type == tokenize.OP and token.string == expected_paren:
                return True
            else:
                return False
        else:
            return False

    def same_types(self, a, b):
        ta = type(a)
        tb = type(b)
        return ta is tb

    def visit_BoolOp(self, node):
        first = True
        for child in node.values:
            if isinstance(child, ast.BoolOp) and not self.same_types(child.op, node.op):
                if first:
                    # There are at least 2 elements in a BoolOp, so for the first, the
                    # tokens are:
                    # "(" (COMMENT? NL)* child (COMMENT? NL)* ")" (COMMENT? NL)* node.op
                    #
                    # Don't look for the open paren because since it's the first element,
                    # the open paren could be something else. For example:
                    #
                    #   f(a and b or c)
                    #
                    # node.values are (roughly) ["a and b", "c"]. There is an open paren
                    # before "a and b" but it's not related to "a and b".
                    # Instead, look for a closing paren between "a and b" and the `node`
                    # bool operator "or".
                    if not self.has_paren(self.tokens[child.last_token.index + 1:], ')'):
                        op_token = self.search_boolop_token(child)
                        self.add_error(
                            "ambiguous precedence between 'or' and 'and'",
                            line=op_token.start[0]
                        )
                else:
                    # Conversely, there must be a `node` bool operator before `child`'s
                    # tokens. Look for an open paren before `child`.
                    # node.op (COMMENT? NL)* "(" (COMMENT? NL)* child (COMMENT? NL)* ")"
                    if not self.has_paren(self.tokens[child.first_token.index - 1::-1], '('):
                        op_token = self.search_boolop_token(child)
                        self.add_error(
                            "ambiguous precedence between 'or' and 'and'",
                            line=op_token.start[0]
                        )

            first = False

        self.generic_visit(node)

    def search_boolop_token(self, node):
        # search for the first and/or operator token
        assert isinstance(node, ast.BoolOp)
        first_operand = node.values[0].last_token
        for token in self.tokens[first_operand.index + 1:]:
            if token.type in (tokenize.NL, tokenize.COMMENT):
                continue
            else:
                assert token.type == tokenize.NAME, "expected an operator after left node"
                assert token.string in ('and', 'or')
                return token
        raise AssertionError("expected an operator after left node")

    def visit_BinOp(self, node):
        if isinstance(node.left, ast.BinOp):
            if not self.check_binop(node, node.left):
                # same as for BoolOp, look for a closing paren after first operand
                if not self.has_paren(self.tokens[node.left.last_token.index + 1:], ')'):
                    op_token = self.search_binop_token(node.left)
                    parent_token = self.search_binop_token(node)
                    self.add_error(
                        f"ambiguous precedence between {parent_token.string!r} and {op_token.string!r}",
                        line=op_token.start[0]
                    )

        if isinstance(node.right, ast.BinOp):
            if not self.check_binop(node, node.right):
                # same as for BoolOp, look for an opening paren before second operand
                if not self.has_paren(self.tokens[node.right.first_token.index - 1::-1], '('):
                    op_token = self.search_binop_token(node.right)
                    parent_token = self.search_binop_token(node)
                    self.add_error(
                        f"ambiguous precedence between {parent_token.string!r} and {op_token.string!r}",
                        line=op_token.start[0]
                    )

        self.generic_visit(node)

    def search_binop_token(self, node):
        # search for the operator token
        assert isinstance(node, ast.BinOp)
        for token in self.tokens[node.left.last_token.index + 1:]:
            if token.type in (tokenize.NL, tokenize.COMMENT):
                continue
            else:
                assert token.type == tokenize.OP, "expected an operator after left node"
                return token
        raise AssertionError("expected an operator after left node")

    def check_binop(self, parent, child):
        if self.same_types(parent.op, child.op):
            return True

        for dubious in dubious_ops:
            if isinstance(parent.op, dubious) and isinstance(child.op, dubious):
                return False

        for dub1, dub2 in dubious_ops_groups:
            if (
                (isinstance(parent.op, dub1) and isinstance(child.op, dub2))
                or (isinstance(parent.op, dub2) and isinstance(child.op, dub1))
            ):
                return False

        return True

    def check(self):
        self.visit(self.tree)
        return self.ok


args = mod['parser'].parse_args()

exit_code = 0
for file in mod['files_to_check'](args):
    verifier = OpPrioVerifier(file)
    if not verifier.check():
        exit_code = 1

sys.exit(exit_code)
