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

import datetime
import os
import sys

from mako.lookup import TemplateLookup

from woob import __version__

WOOB_MODULES = os.getenv(
    'WOOB_MODULES',
    os.path.realpath(os.path.join(os.path.dirname(__file__), '../../modules')))
BOILERPLATE_PATH = os.getenv(
    'BOILERPLATE_PATH',
    os.path.realpath(os.path.join(os.path.dirname(__file__), 'boilerplate_data')))

TEMPLATES = TemplateLookup(directories=[BOILERPLATE_PATH], input_encoding='utf-8')


def write(target, contents):
    if not os.path.isdir(os.path.dirname(target)):
        os.makedirs(os.path.dirname(target))
    if os.path.exists(target):
        print(f"{target} already exists.", file=sys.stderr)
        sys.exit(4)
    with open(target, mode='w', encoding='utf-8') as f:
        f.write(contents)
    print(f'Created {target}')


class Recipe:
    NAME = None

    @classmethod
    def configure_subparser(cls, subparsers):
        subparser = subparsers.add_parser(cls.NAME)
        subparser.add_argument('name', help='Module name')
        subparser.set_defaults(recipe_class=cls)
        return subparser

    def __init__(self, args):
        self.name = args.name.lower().replace(' ', '')
        self.classname = args.name.title().replace(' ', '').replace('_', '')
        self.description = args.name.title().replace('_', ' ')
        self.year = datetime.date.today().year
        self.author = args.author
        self.email = args.email
        self.version = __version__
        self.login = False

    def write(self, filename, contents):
        return write(os.path.join(WOOB_MODULES, self.name, filename), contents)

    def template(self, name, **kwargs):
        if '.' not in name:
            name += '.pyt'
        return TEMPLATES.get_template(name) \
            .render(r=self,
                    # workaround, as it's also a mako directive
                    login=self.login,
                    **kwargs).strip() + '\n'

    def generate(self):
        raise NotImplementedError()
