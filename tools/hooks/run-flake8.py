#!/usr/bin/env python3

import os
import runpy
import sys
from pathlib import Path

from flake8.main.cli import main


mod = runpy.run_path(str(Path(__file__).with_name('checkerlib.py')))

args = mod['parser'].parse_args()

opts = []
if os.getenv("GITLAB_CI"):
    opts = [
        "--format=gl-codeclimate",
        "--output-file=gl-qa-report-flake8-strict.json",
    ]

# E501: Line too long
#   Disabled because it doesn't allow exceptions, for example URLs or log
#   messages shouldn't be split, less readable or searchable.
# W503: Line break occurred before a binary operator
#   Disabling it follows pep8 (see W504).
# E266: Too many leading '#' for block comment
#   But it's a nice visual separator sometimes.
result = main([
    '--ignore=E501,W503,E266',
    *opts,
    *map(str, mod['files_to_check'](args)),
])

sys.exit(result)
