#!/usr/bin/env python3

import ast
from collections import namedtuple
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

        if getattr(node, attr)[0]:
            first_elt_token = getattr(node, attr)[0].first_token
        else:
            assert isinstance(node, ast.Dict) and attr == 'keys', "None node should only be in dict keys"
            # a None node in ast.Dict.keys happens in case of **mapping
            # use the tokens of the value then, nevermind the "**" tokens
            first_elt_token = node.values[0].first_token

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

    def visit_ImportFrom(self, node):
        assert node.first_token.string == 'from'  # asttokens bug
        proc = SetTokensOnImport(node, self.tokens[node.first_token.index:node.last_token.index + 1])
        proc.process()

        # TODO reimplement using tokens only, we don't really need the AST for imports
        self.check_trailing(node, 'names')

    def check(self):
        self.visit(self.tree)
        return self.ok


class Tokens:
    Matcher = namedtuple('Matcher', ('type', 'string'))
    # string = None means whatever string

    FROM = Matcher(tokenize.NAME, 'from')
    IMPORT = Matcher(tokenize.NAME, 'import')
    AS = Matcher(tokenize.NAME, 'as')
    ANY_NAME = Matcher(tokenize.NAME, None)

    DOT = Matcher(tokenize.OP, '.')
    COMMA = Matcher(tokenize.OP, ',')
    OPEN = Matcher(tokenize.OP, '(')
    CLOSE = Matcher(tokenize.OP, ')')
    STAR = Matcher(tokenize.OP, '*')


class RuleBase:
    # helper for passing in a stream of tokens and checking if we have the desired tokens

    def __init__(self, tokens):
        self.tokens = tokens
        self.current = 0

    @staticmethod
    def token_match(token, matcher):
        if matcher.type != token.type:
            return False
        if matcher.string is not None and matcher.string != token.string:
            return False
        return True

    def peek(self):
        # just peek current token without advancing cursor
        return self.tokens[self.current]

    def peek_prev(self):
        assert self.current > 0
        return self.tokens[self.current - 1]

    def peek_normal(self):
        # peek the first non-NL, non-COMMENT token
        # (and advance reading cursor to it)
        while self.current < len(self.tokens):
            token = self.tokens[self.current]
            if token.type not in (tokenize.NL, tokenize.COMMENT):
                return token
            self.current += 1

    def read(self):
        # get current token and advance cursor
        val = self.peek()
        self.current += 1
        return val

    def has(self, matcher):
        token = self.peek_normal()
        if token is None:
            # end of tokens
            return False

        return self.token_match(token, matcher)

    def probe(self, matcher):
        # if token matches, advances cursor
        # else, stay in place
        if self.has(matcher):
            self.current += 1
            return True
        return False

    def match(self, matcher):
        assert self.probe(matcher)


class SetTokensOnImport(RuleBase):
    # this is due to https://github.com/gristlabs/asttokens/issues/60
    # we browse the given Import node and set the correct tokens as first_token/last_token
    # token sequences are listed in https://docs.python.org/3/reference/simple_stmts.html#the-import-statement

    def __init__(self, node, tokens):
        super().__init__(tokens)
        self.node = node
        self.aliases_iter = iter(node.names)
        self.current_alias = None

    def process(self):
        if self.probe(Tokens.IMPORT):
            # "import foo" and related forms
            self.do_basic_import()
        elif self.probe(Tokens.FROM):
            # "from foo import bar" and related forms
            self.do_from_import()
        else:
            raise AssertionError('nothing was probed')

    def do_basic_import(self):
        self.do_module_as()
        while self.probe(Tokens.COMMA):
            self.do_module_as()

    def do_from_import(self):
        while self.probe(Tokens.DOT):
            # example: from .foo import bar
            pass

        if not self.probe(Tokens.IMPORT):
            # here, we are not in: from . import foo
            self.do_module()
            self.match(Tokens.IMPORT)

        if self.probe(Tokens.STAR):
            # example: from foo import *
            return

        paren = self.probe(Tokens.OPEN)

        self.do_identifier_as()
        while self.probe(Tokens.COMMA):
            if not self.has(Tokens.ANY_NAME):
                # that was a trailing comma
                break
            self.do_identifier_as()

        if paren:
            self.match(Tokens.CLOSE)

    def do_module_as(self):
        # match: module ["as" identifier]
        # and set tokens on nodes
        self.current_alias = next(self.aliases_iter)
        self.current_alias.first_token = self.peek_normal()
        self.do_module()
        self.current_alias.last_token = self.peek_prev()

        if self.probe(Tokens.AS):
            self.match(Tokens.ANY_NAME)
            self.current_alias.last_token = self.peek_prev()

    def do_identifier_as(self):
        # match: identifier ["as" identifier]
        # and set tokens on nodes
        self.current_alias = next(self.aliases_iter)
        self.current_alias.first_token = self.peek_normal()
        self.current_alias.last_token = self.peek()
        self.match(Tokens.ANY_NAME)

        if self.probe(Tokens.AS):
            self.match(Tokens.ANY_NAME)
            self.current_alias.last_token = self.peek_prev()

    def do_module(self):
        # match: identifier ("." identifier)*
        self.match(Tokens.ANY_NAME)
        while self.probe(Tokens.DOT):
            self.match(Tokens.ANY_NAME)


args = mod['parser'].parse_args()

exit_code = 0
for file in mod['files_to_check'](args):
    verifier = TrailingCommaVerifier(file)
    if not verifier.check():
        exit_code = 1

sys.exit(exit_code)
