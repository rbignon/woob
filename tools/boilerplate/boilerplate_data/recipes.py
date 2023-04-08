# Copyright(C) 2013-2021      Sébastien Jean
#
# This file is part of woob.
#
# woob is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# woob is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with woob. If not, see <http://www.gnu.org/licenses/>.

import inspect
import importlib
import sys
import pkgutil

import woob.capabilities

from recipe import Recipe


__all__ = ['BaseRecipe', 'CapRecipe']


class BaseRecipe(Recipe):
    NAME = 'base'

    def generate(self):
        self.write('__init__.py', self.template('init'))
        self.write('module.py', self.template('base_module'))
        self.write('browser.py', self.template('base_browser'))
        self.write('pages.py', self.template('base_pages'))
        self.write('test.py', self.template('base_test'))
        self.write('requirements.txt', self.template('requirements.txt'))


class CapRecipe(Recipe):
    NAME = 'cap'

    def __init__(self, args):
        super().__init__(args)
        self.capname = args.capname

        PREFIX = 'woob.capabilities.'
        if not self.capname.startswith(PREFIX):
            self.capname = PREFIX + self.capname

        try:
            self.capmodulename, self.capname = self.capname.rsplit('.', 1)
        except ValueError:
            self.error('Cap name must be in format module.CapSomething or CapSomething')

        self.login = args.login
        self.methods = []

    @classmethod
    def configure_subparser(cls, subparsers):
        subparser = super().configure_subparser(subparsers)
        subparser.add_argument('--login', action='store_true', help='The site requires login')
        subparser.add_argument('capname', help='Capability name')
        return subparser

    def find_module_cap(self):
        if '.' not in self.capname:
            return self.search_cap()

        try:
            module = importlib.import_module(self.capmodulename)
        except ImportError:
            self.error(f'Module {self.capmodulename} not found')
        try:
            cap = getattr(module, self.capname)
        except AttributeError:
            self.error(f'Module {self.capmodulename} has no such capability {self.capname}')
        return cap

    def search_cap(self):
        modules = pkgutil.walk_packages(woob.capabilities.__path__, prefix='woob.capabilities.')
        for _, capmodulename, __ in modules:
            module = importlib.import_module(capmodulename)
            if hasattr(module, self.capname):
                self.capmodulename = capmodulename
                return getattr(module, self.capname)

        self.error(f'Capability {self.capname} not found')
        return None

    def error(self, message):
        print(message, file=sys.stderr)
        sys.exit(1)

    def methods_code(self, klass):
        methods = []

        for name, member in inspect.getmembers(klass):
            if inspect.isfunction(member) and name in klass.__dict__:
                lines, _ = inspect.getsourcelines(member)
                methods.append(lines)

        return methods

    def generate(self):
        cap = self.find_module_cap()

        self.methods = self.methods_code(cap)

        self.write('__init__.py', self.template('init'))
        self.write('module.py', self.template('cap_module'))
        self.write('browser.py', self.template('base_browser'))
        self.write('pages.py', self.template('base_pages'))
        self.write('test.py', self.template('base_test'))
        self.write('requirements.txt', self.template('requirements.txt'))
