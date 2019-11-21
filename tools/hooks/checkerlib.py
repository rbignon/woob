# python3-only

import argparse
from pathlib import Path
import subprocess


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
                git_root / 'weboob/**/*.py',
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
