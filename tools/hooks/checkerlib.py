# python3-only

import ast
import argparse
from pathlib import Path
import subprocess
import sys
import tokenize


def get_lines(cmd):
    return subprocess.check_output(cmd, encoding='utf-8').strip('\n').split('\n')


parser = argparse.ArgumentParser()
parser.add_argument('files', nargs='*')

current_file = Path(__file__).resolve()
git_root = current_file.parent.parent.parent


def files_to_check(args, pattern=None):
    if pattern is None:
        pattern = '^# flake8: compatible'

    if args.files:
        to_check = args.files
    else:
        try:
            to_check = get_lines([
                'git', 'grep', '-l', pattern,
                git_root / 'modules/**/*.py',  # git will interpret wildcards by itself
                git_root / 'woob/**/*.py',
            ])
        except subprocess.CalledProcessError as exc:
            if exc.returncode != 1:
                raise
            # when no results found
            to_check = []

    return to_check


def run_on_files(cmd):
    args = parser.parse_args()
    to_check = files_to_check(args)
    if to_check:
        subprocess.check_call([*cmd, *to_check])


def parse_tokens(filename):
    with open(filename) as fd:
        tokens = list(tokenize.generate_tokens(fd.readline))
    return tokens


class Checker:
    def __init__(self, filename):
        super().__init__()

        self.filename = filename
        self.noqa_lines = set()
        self.tokens = None
        self.ok = True

    def parse_tokens(self):
        self.tokens = parse_tokens(self.filename)

    def parse_ast(self):
        with open(self.filename) as fd:
            self.tree = ast.parse(fd.read(), self.filename)

    def parse_noqa(self):
        if self.tokens is None:
            self.parse_tokens()

        for token in self.tokens:
            if token.type == tokenize.COMMENT and token.string == "# noqa":
                self.noqa_lines.add(token.start[0])

    def add_error(self, message, line, col=None, code=None):
        if line in self.noqa_lines:
            return

        col_text = ''
        if col is not None:
            col_text = f"{col}:"

        code_text = ''
        if code is not None:
            code_text = f" {code}"

        print(
            f"{self.filename}:{line}:{col_text}{code_text} {message}",
            file=sys.stderr
        )
        self.ok = False
