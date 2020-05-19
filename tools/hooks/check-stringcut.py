#!/usr/bin/env python3

from pathlib import Path
import runpy
import sys
import tokenize


mod = runpy.run_path(str(Path(__file__).with_name('checkerlib.py')))
Checker = mod['Checker']

# typical code that we absolutely want to prevent (look closely at the commas):
#   foo = URL(
#       "/one/url/",
#       "/a/second/url"
#       "/that/is/actually"
#       "/very/long",
#       "/and/a/third/url"
#   )


class StringChecker(Checker):
    def __init__(self, filename):
        super().__init__(filename)
        self.parse_tokens()

    def check_strings(self):
        # STRING NEWLINE STRING: ok
        # STRING (COMMENT? NL)* STRING: bad

        in_str = False
        for token in self.tokens:
            if token.type == tokenize.STRING:
                self.check_continuation(token)

            if in_str:
                if token.type == tokenize.STRING:
                    self.add_error(
                        "implicitly concatenated strings are forbidden",
                        line=token.start[0], col=token.start[1],
                    )
                elif token.type not in (tokenize.NL, tokenize.COMMENT):
                    in_str = False
            elif token.type == tokenize.STRING:
                in_str = True

        return self.ok

    # check_continuation avoids such code:
    #   foo = "bar\
    #   baz"

    def check_continuation(self, token):
        if (
            token.start[0] == token.end[0]
            or token.string.endswith('"""') or token.string.endswith("'''")
        ):
            return True

        assert '\\\n' in token.string
        self.add_error(
            "line-continuations in a string are forbidden",
            line=token.start[0], col=token.start[1],
        )


args = mod['parser'].parse_args()

exit_code = 0
for file in mod['files_to_check'](args):
    checker = StringChecker(file)
    checker.parse_noqa()
    if not checker.check_strings():
        exit_code = 1

sys.exit(exit_code)
