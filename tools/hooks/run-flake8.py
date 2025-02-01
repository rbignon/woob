#!/usr/bin/env python3

import os
import runpy
import sys
from pathlib import Path

from flake8.main.cli import main


mod = runpy.run_path(str(Path(__file__).with_name("checkerlib.py")))

args = mod["parser"].parse_args()

opts = []
if os.getenv("GITLAB_CI"):
    opts = [
        "--format=gl-codeclimate",
        "--output-file=gl-qa-report-flake8-strict.json",
    ]

result = main(
    [
        *opts,
        *map(str, mod["files_to_check"](args)),
    ]
)

sys.exit(result)
