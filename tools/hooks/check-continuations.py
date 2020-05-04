#!/usr/bin/env python3

from pathlib import Path
import runpy
import sys
import tokenize


def check_lines(tokens, filename):
    ok = True

    previous_token = None
    for token in tokens:
        if token.type in (tokenize.NEWLINE, tokenize.NL):
            previous_token = None
            continue

        # if two adjacent tokens don't "touch" on the same line
        # and no NL/NEWLINE is involved, it's a line continuation!
        if previous_token and previous_token.end[0] != token.start[0]:
            assert previous_token.line.endswith('\\\n')
            ok = False
            print(
                f"{filename}:{token.start[0]}:{token.start[1]}: backslashed line-continuations are forbidden",
                file=sys.stderr
            )

        previous_token = token

    return ok


mod = runpy.run_path(str(Path(__file__).with_name('checkerlib.py')))

args = mod['parser'].parse_args()

exit_code = 0
for file in mod['files_to_check'](args):
    with open(file) as fd:
        tokens = list(tokenize.generate_tokens(fd.readline))

    if not check_lines(tokens, file):
        exit_code = 1

sys.exit(exit_code)
