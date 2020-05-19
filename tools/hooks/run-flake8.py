#!/usr/bin/env python3

from pathlib import Path
import runpy
import subprocess
import sys


mod = runpy.run_path(str(Path(__file__).with_name('checkerlib.py')))

# E501: Line too long
#   Disabled because it doesn't allow exceptions, for example URLs or log
#   messages shouldn't be split, less readable or searchable.
# W503: Line break occurred before a binary operator
#   Disabling it follows pep8 (see W504).
# E266: Too many leading '#' for block comment
#   But it's a nice visual separator sometimes.

args = mod['parser'].parse_args()

exit_code = 0
for file in mod['files_to_check'](args):
    try:
        subprocess.check_call([
            'flake8', '--ignore=E501,W503,E266',
            str(file),
        ])
    except subprocess.CalledProcessError:
        exit_code = 1

sys.exit(exit_code)
