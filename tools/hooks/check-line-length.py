#!/usr/bin/env python3

from pathlib import Path
import runpy
import sys
import token as token_mod
import tokenize


def check_lines(tokens, file):
    ok = True
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

    for token in tokens:
        if token.type == token_mod.STRING:
            if token.start[1] + 1 >= args.line_length:
                ok = False
                print(
                    f"{file}:{token.start[0]}: string starts after max line length",
                    file=sys.stderr
                )
            elif token.end[1] >= args.line_length:
                crossing = True

        elif token.type == token_mod.COMMENT:
            if token.start[1] + 1 >= args.line_length:
                ok = False
                print(
                    f"{file}:{token.start[0]}: comment starts after max line length",
                    file=sys.stderr
                )
            elif token.end[1] >= args.line_length:
                crossing = True

        elif token.type in (token_mod.NL, token_mod.NEWLINE):
            if token.start[1] > args.line_length and not crossing:
                if not offending_token:
                    offending_token = token
                print(
                    f"{file}:{offending_token.start[0]}: line too long not due to a string",
                    file=sys.stderr
                )
            crossing = False
            offending_token = None

        elif token.type != token_mod.OP:
            if not offending_token:
                offending_token = token
            crossing = False

    return ok


mod = runpy.run_path(str(Path(__file__).with_name('checkerlib.py')))

parser = mod['parser']
parser.add_argument('-l', '--line-length', type=int, default=80)
args = parser.parse_args()

exit_code = 0
for file in mod['files_to_check'](args):
    with open(file) as fd:
        tokens = list(tokenize.generate_tokens(fd.readline))

    if not check_lines(tokens, file):
        exit_code = 1

sys.exit(exit_code)
