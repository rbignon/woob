#!/usr/bin/env python3

from pathlib import Path
import runpy
import sys
import tokenize


mod = runpy.run_path(str(Path(__file__).with_name('checkerlib.py')))
Checker = mod['Checker']


class ContinuationChecker(Checker):
    def __init__(self, filename):
        super().__init__(filename)
        self.parse_tokens()

    def check_lines(self):
        previous_token = None
        for token in self.tokens:
            if token.type in (tokenize.NEWLINE, tokenize.NL):
                previous_token = None
                continue

            # if two adjacent tokens don't "touch" on the same line
            # and no NL/NEWLINE is involved, it's a line continuation!
            if previous_token and previous_token.end[0] != token.start[0]:
                assert previous_token.line.endswith('\\\n')
                self.add_error(
                    "backslashed line-continuations are forbidden",
                    line=token.start[0], col=token.start[1],
                )

            previous_token = token

        return self.ok


args = mod['parser'].parse_args()

exit_code = 0
for file in mod['files_to_check'](args):
    checker = ContinuationChecker(file)
    checker.parse_noqa()
    if not checker.check_lines():
        exit_code = 1

sys.exit(exit_code)
