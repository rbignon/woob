#!/usr/bin/env python3

import os
import re
import subprocess
from pathlib import Path


def get_lines(command):
    proc = subprocess.run(command, encoding="utf-8", stdout=subprocess.PIPE)
    text = proc.stdout.strip()
    if text:
        return text.split("\n")
    # XXX for some reason, "".split(...) == [""]
    # and we don't want this curiosity
    return []


def search_dependencies(command, pattern):
    dependencies = {}
    regex = re.compile(pattern, re.M)

    for srcfile in get_lines(command):
        srcfile = Path(srcfile).resolve()
        module_name = srcfile.relative_to(gitroot / "modules").parts[0]
        for matches in regex.findall(srcfile.read_text()):
            parent_name = next(filter(None, matches))
            dependencies.setdefault(module_name, set()).add(parent_name)

    return dependencies


os.chdir(Path(__file__).parent.parent)
gitroot = Path.cwd()

dependencies = search_dependencies(["git", "grep", "-l", "PARENT", "modules"], r"""^\s+PARENT = ["'](\w+)["']()$""")

dependencies.update(
    search_dependencies(
        ["git", "grep", "-l", "woob_modules", "modules"],
        r"""^from woob_modules\.(\w+)\b(?:.*) import |import woob_modules\.(\w+)\b""",
    )
)

deps_regex = re.compile(r"^(\s+)DEPENDENCIES = .*$", re.M)
version_regex = re.compile(r"^(\s+)(VERSION = .*)$", re.M)

for module_name in dependencies:
    module_path = gitroot / "modules" / module_name / "module.py"
    source = module_path.read_text()

    deps_tuple = tuple(sorted(dependencies[module_name]))
    if deps_regex.search(source):
        source = deps_regex.sub(fr"\1DEPENDENCIES = {deps_tuple!r}", source)
    else:
        source = version_regex.sub(fr"\1\2\n\1DEPENDENCIES = {deps_tuple!r}", source)

    module_path.write_text(source)
