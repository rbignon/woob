#!/usr/bin/env python3

from pathlib import Path
import runpy
import sys
from types import ModuleType

from flake8.main.cli import main
from flake8_import_order.styles import PEP8
import pkg_resources


mod = runpy.run_path(str(Path(__file__).with_name('checkerlib.py')))

args = mod['parser'].parse_args()


# flake8-import-order's PEP8 style merges app imports and relative imports
class AllSeparateStyle(PEP8):
    @staticmethod
    def same_section(previous, current):
        return current.type == previous.type


# flake8-import-order is almost only configurable through entry_points
# ugly hack to avoid having to create a separate package with entry_point, setup, etc.
style_mod = ModuleType('fake_module_all_separate')
style_mod.AllSeparateStyle = AllSeparateStyle
sys.modules['fake_module_all_separate'] = style_mod

d = pkg_resources.Distribution('/lol.py')
ep = pkg_resources.EntryPoint.parse('fake_module_all_separate = fake_module_all_separate:AllSeparateStyle')
ep.dist = d
d._ep_map = {'flake8_import_order.styles': {'fake_module_all_separate': ep}}
pkg_resources.working_set.add(d, 'fake_module_all_separate')


# E501: Line too long
#   Disabled because it doesn't allow exceptions, for example URLs or log
#   messages shouldn't be split, less readable or searchable.
# W503: Line break occurred before a binary operator
#   Disabling it follows pep8 (see W504).
# E266: Too many leading '#' for block comment
#   But it's a nice visual separator sometimes.
main([
    '--ignore=E501,W503,E266',
    '--application-import-names=weboob,woob',
    '--import-order-style=fake_module_all_separate',
    *map(str, mod['files_to_check'](args)),
])
