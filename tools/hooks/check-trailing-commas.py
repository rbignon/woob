#!/usr/bin/env python3

import ast
from pathlib import Path
import runpy
import sys
import tokenize

from asttokens import ASTTokens


mod = runpy.run_path(str(Path(__file__).with_name('checkerlib.py')))
Checker = mod['Checker']

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


class TrailingCommaVerifier(Checker, ast.NodeVisitor):
    def __init__(self, filename):
        super().__init__(filename)
        with open(self.filename) as fd:
            self.astt = ASTTokens(fd.read(), parse=True)
        self.tree = self.astt.tree
        self.tokens = self.astt.tokens

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

        all_tokens = self.tokens

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
            self.add_error(
                'expected a comma after element',
                line=last_elt_token.end[0],
            )
        elif not has_nl:
            self.add_error(
                'expected end of line between comma and literal end',
                line=last_elt_token.end[0],
            )

    def check_first_indent(self, node, attr):
        if self.should_skip(node, attr):
            return

        first_elt_token = getattr(node, attr)[0].first_token
        if first_elt_token.start[0] == node.first_token.start[0]:
            self.add_error(
                'first element should start on a new line',
                line=first_elt_token.start[0],
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

    def visit_Call(self, node):
        assert node.last_token.string == ')'

        self.generic_visit(node)

        if not (node.args or node.keywords):
            # no params at all, don't bother
            return

        callable_last = node.func.last_token
        # for call "(foo)(bar)", node.func.last_token is "foo"
        # after callable_last, there must be only this:
        #   (COMMENT? NL)* RPAR* (COMMENT? NL)* LPAR
        for token in self.tokens[callable_last.index + 1:]:
            if token.type == tokenize.OP:
                if token.string == '(':
                    open_paren = token
                    break

                assert token.string == ')'
            else:
                assert token.type in (tokenize.NL, tokenize.COMMENT)
        else:
            raise AssertionError('could not find opening paren')

        if open_paren.start[0] == node.last_token.start[0]:
            # '(' and ')' on the same line
            return

        if node.args:
            param_first_token = node.args[0].first_token
        else:
            assert node.keywords
            # here we go again, the keyword is just a string, no .token attribute

            for token in self.tokens[open_paren.index + 1:]:
                if token.type == tokenize.NAME:
                    param_first_token = token
                    break
                elif token.type == tokenize.OP:
                    assert token.string == '**' and not node.keywords[0].arg
                    param_first_token = token
                    break
                assert token.type in (tokenize.NL, tokenize.COMMENT)
            else:
                raise AssertionError('could not find first keyword')

        if open_paren.start[0] == param_first_token.start[0]:
            # allow compact multiline call if single parameter
            # e.g. "foo([\n1,\n2,\n])"
            if (
                len(node.args) == 1 and not node.keywords
                and node.last_token.end[0] == node.args[0].last_token.end[0]
            ):
                return
            elif (
                len(node.keywords) == 1 and not node.args
                and node.last_token.end[0] == node.keywords[0].value.last_token.end[0]
            ):
                return

            self.add_error(
                'first param should start on a new line',
                line=param_first_token.start[0],
            )

    def check(self):
        self.visit(self.tree)
        return self.ok


args = mod['parser'].parse_args()

exit_code = 0
for file in mod['files_to_check'](args):
    verifier = TrailingCommaVerifier(file)
    if not verifier.check():
        exit_code = 1

sys.exit(exit_code)
