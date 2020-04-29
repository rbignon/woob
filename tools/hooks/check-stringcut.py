#!/usr/bin/env python3

from pathlib import Path
import runpy
import sys
import token as token_mod
import tokenize


# typical code that we absolutely want to prevent (look closely at the commas):
#   foo = URL(
#       "/one/url/",
#       "/a/second/url"
#       "/that/is/actually"
#       "/very/long",
#       "/and/a/third/url"
#   )

def check_strings(tokens, filename):
    ok = True

    # STRING NEWLINE STRING: ok
    # STRING (COMMENT? NL)* STRING: bad

    in_str = False
    for token in tokens:
        if token.type == token_mod.STRING:
            ok = check_continuation(token, filename) and ok

        if in_str:
            if token.type == token_mod.STRING:
                print(
                    f"{filename}:{token.start[0]}:{token.start[1]}: implicitly concatenated strings are forbidden",
                    file=sys.stderr
                )
                ok = False
            elif token.type not in (token_mod.NL, token_mod.COMMENT):
                in_str = False
        elif token.type == token_mod.STRING:
            in_str = True

    return ok


# check_continuation avoids such code:
#   foo = "bar\
#   baz"

def check_continuation(token, filename):
    if (
        token.start[0] == token.end[0]
        or token.string.endswith('"""') or token.string.endswith("'''")
    ):
        return True

    assert '\\\n' in token.string
    print(
        f"{filename}:{token.start[0]}:{token.start[1]}: line-continuations in a string are forbidden",
        file=sys.stderr
    )
    return False


mod = runpy.run_path(str(Path(__file__).with_name('checkerlib.py')))

args = mod['parser'].parse_args()

exit_code = 0
for file in mod['files_to_check'](args):
    with open(file) as fd:
        tokens = list(tokenize.generate_tokens(fd.readline))

    if not check_strings(tokens, file):
        exit_code = 1

sys.exit(exit_code)
