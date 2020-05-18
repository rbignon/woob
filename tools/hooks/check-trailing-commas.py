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
    ok = True

    def should_skip(self, node, attr):
        if not getattr(node, attr):
            # it's an empty container
            return True
        first_elem = getattr(node, attr)[0]

        return (
            # that's not multiline, we don't care
            node.first_token.start[0] == node.last_token.start[0]
            # single multiline element, acceptable for compacity if glued to container
            # e.g. [[[\n1,\n2,\n3,\n]]]
            or (
                len(getattr(node, attr)) == 1
                and node.first_token.start[0] == first_elem.first_token.start[0]
                and node.last_token.end[0] == first_elem.last_token.end[0]
            )
        )

    def check_trailing(self, node, attr):
        if self.should_skip(node, attr):
            return

        last_elt_token = getattr(node, attr)[-1].last_token
        # for list "[0,(1+2),]", last_elt_token is "2"
        # after last_elt_token, we want this:
        #   RPAR* COMMA (COMMENT? NL)+ end-delimiter

        all_tokens = self.src.astt.tokens

        has_comma = False
        has_nl = False
        for idx in range(last_elt_token.index + 1, node.last_token.index):
            if all_tokens[idx].type == tokenize.OP:
                if all_tokens[idx].string == ',':
                    assert not has_comma
                    has_comma = True
                else:
                    assert all_tokens[idx].string == ')'

            elif all_tokens[idx].type == tokenize.NL:
                has_nl = True
                break

            else:
                assert all_tokens[idx].type == tokenize.COMMENT

        if not has_comma:
            self.ok = False
            print(
                f'{self.src.path}:{last_elt_token.end[0]}: expected a comma after element',
                file=sys.stderr
            )
        elif not has_nl:
            self.ok = False
            print(
                f'{self.src.path}:{last_elt_token.end[0]}: expected end of line between comma and literal end',
                file=sys.stderr
            )

    def check_first_indent(self, node, attr):
        if self.should_skip(node, attr):
            return

        first_elt_token = getattr(node, attr)[0].first_token
        if first_elt_token.start[0] == node.first_token.start[0]:
            self.ok = False
            print(
                f'{self.src.path}:{first_elt_token.start[0]}: first element should start on a new line',
                file=sys.stderr
            )

    def visit_Tuple(self, node):
        # no assert to verify tokens, because there might be no delimiters:
        #   foo = a, b  # no parentheses around that tuple
        # such a tuple cannot be multiline, so we won't check trailing commas
        self.visit_simple_container(node)

    def visit_simple_container(self, node):
        self.check_trailing(node, 'elts')
        self.check_first_indent(node, 'elts')
        self.generic_visit(node)

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
        self.check_first_indent(node, 'keys')
        self.generic_visit(node)


mod = runpy.run_path(str(Path(__file__).with_name('checkerlib.py')))

args = mod['parser'].parse_args()

exit_code = 0
for file in mod['files_to_check'](args):
    source = FileSource(file)
    proc = Processor(source)

    verifier = TrailingCommaVerifier()
    proc.verify(verifier)
    if not verifier.ok:
        exit_code = 1

sys.exit(exit_code)
