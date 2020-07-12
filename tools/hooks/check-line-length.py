#!/usr/bin/env python3

from pathlib import Path
import runpy
import sys
import tokenize


mod = runpy.run_path(str(Path(__file__).with_name('checkerlib.py')))
Checker = mod['Checker']


class LineLengthChecker(Checker):
    def __init__(self, filename):
        super().__init__(filename)
        self.parse_tokens()

    def check_lines(self):
        crossing = False
        offending_token = None

        # string and comments are the only tokens that are allowed to cross line border
        # for comments, only NL or NEWLINE can be after COMMENT
        #   STRING OP* (NL | NEWLINE): ok
        #   STRING

        # .start[0]: line number of start, starting at 1
        # .end[0]:   line number of end, included, starting at 1
        # .start[1]: column number of start, starting at 0
        # .end[1]:   column number of end, excluded, starting at 0
        # ->
        # .start[1] + 1 == column number of start, starting at 1
        # .end[1] == column number of end, included, starting at 1

        for token in self.tokens:
            if token.type == tokenize.STRING:
                if token.start[1] + 1 >= args.line_length:
                    self.add_error(
                        "string starts after max line length",
                        line=token.start[0]
                    )
                elif token.end[1] >= args.line_length:
                    crossing = True

            elif token.type == tokenize.COMMENT:
                if token.start[1] + 1 >= args.line_length:
                    self.add_error(
                        "comment starts after max line length",
                        line=token.start[0]
                    )
                elif token.end[1] >= args.line_length:
                    crossing = True

            elif token.type in (tokenize.NL, tokenize.NEWLINE):
                if token.start[1] > args.line_length and not crossing:
                    if not offending_token:
                        offending_token = token

                    self.add_error(
                        "line too long not due to a string",
                        line=offending_token.start[0]
                    )
                crossing = False
                offending_token = None

            elif token.type != tokenize.OP:
                if not offending_token:
                    offending_token = token
                crossing = False

        return self.ok


parser = mod['parser']
parser.add_argument('-l', '--line-length', type=int, default=80)
args = parser.parse_args()

exit_code = 0
for file in mod['files_to_check'](args):
    checker = LineLengthChecker(file)
    checker.parse_noqa()
    if not checker.check_lines():
        exit_code = 1

sys.exit(exit_code)
