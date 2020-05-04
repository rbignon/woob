#!/usr/bin/env python3

import ast
from collections import defaultdict
from pathlib import Path
import runpy
import sys
import tokenize

from asttokens import ASTTokens


# these are ok:
#   {1: 2, 3: 4}
#   {
#       1: 2,
#   }
#   {
#       1: 2,  # foo
#   }
# these are bad:
#   {
#       1: 2
#   }
#   {
#       1: 2
#       ,
#   }
#   {
#       1: 2,}


class FileSource:
    def __init__(self, path):
        self.path = path
        with open(path) as fd:
            self.astt = ASTTokens(fd.read(), parse=True)


class Processor:
    def __init__(self, src):
        self.src = src
        self.errors = defaultdict(list)

    def add_error(self, token, message):
        self.errors[token.start[0]].append(
            f"{token.line.rstrip()}\n"
            f"{' ' * token.start[1]}^ {message}"
        )

    def print_errors(self):
        for l in sorted(self.errors):
            for err in self.errors[l]:
                print(f'{self.src.path}:{l}:')
                print(f'{err}')

    def verify(self, verifier):
        verifier.verify(self.src, self)


class AstVerifier(ast.NodeVisitor):
    def verify(self, src, proc):
        self.src = src
        self.proc = proc
        self.visit(self.src.astt.tree)


class TrailingCommaVerifier(AstVerifier):
    def check_trailing(self, node, attr):
        if (
            # that's not multiline, we don't care
            node.first_token.start[0] == node.last_token.start[0]
            # or it's an empty container
            or not getattr(node, attr)
        ):
            return self.generic_visit(node)

        # for list "[0,1+2,]", last_elt_token is "2"
        last_elt_token = getattr(node, attr)[-1].last_token
        # after last_elt_token, we want this:
        #   COMMA (COMMENT? NL)+ end-delimiter

        all_tokens = self.src.astt.tokens
        if all_tokens[last_elt_token.index + 1].string != ',':
            self.proc.add_error(all_tokens[last_elt_token.index + 1], 'expected a comma after element')
            return

        # since we start from last element, there can't be anything other than
        # COMMENT and NL, but what we want to ensure is there's at least one NL
        for idx in range(last_elt_token.index + 2, node.last_token.index + 1):
            if all_tokens[idx].type == tokenize.NL:
                break
        else:
            self.proc.add_error(node.last_token, 'expected end of line between comma and literal end')

    def visit_Tuple(self, node):
        # no assert to verify tokens, because there might be no delimiters:
        #   foo = a, b  # no parentheses around that tuple
        # such a tuple cannot be multiline, so we won't check trailing commas
        self.visit_simple_container(node)

    def visit_simple_container(self, node):
        self.check_trailing(node, 'elts')
        for sub in node.elts:
            self.visit(sub)

    def visit_List(self, node):
        assert node.first_token.string == '['
        assert node.last_token.string == ']'
        self.visit_simple_container(node)

    def visit_Set(self, node):
        assert node.first_token.string == '{'
        assert node.last_token.string == '}'
        self.visit_simple_container(node)

    def visit_Dict(self, node):
        assert node.first_token.string == '{'
        assert node.last_token.string == '}'

        self.check_trailing(node, 'values')

        for sub in node.keys:
            self.visit(sub)
        for sub in node.values:
            self.visit(sub)


mod = runpy.run_path(str(Path(__file__).with_name('checkerlib.py')))

args = mod['parser'].parse_args()

exit_code = 0
for file in mod['files_to_check'](args):
    source = FileSource(file)
    proc = Processor(source)

    proc.verify(TrailingCommaVerifier())
    if proc.errors:
        proc.print_errors()
        exit_code = 1

sys.exit(exit_code)
