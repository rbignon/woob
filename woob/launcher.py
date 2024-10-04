# Copyright(C) 2009-2021  Romain Bignon
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

import sys
import difflib
import importlib
import pkgutil

import woob
import woob.applications

try:
    import woob_applications
except ImportError:
    woob_applications = None


__all__ = ['Launcher']


class Launcher:
    @classmethod
    def list_apps(cls):
        apps = set()
        for module in pkgutil.iter_modules(woob.applications.__path__):
            apps.add(module.name)

        if woob_applications:
            for module in pkgutil.iter_modules(woob_applications.__path__):
                apps.add(module.name)

        apps.remove("main")
        return sorted(apps)

    @classmethod
    def load_app(cls, app):
        try:
            app_module = importlib.import_module("woob.applications.%s" % app)
        except ImportError:
            if woob_applications is None:
                raise
            app_module = importlib.import_module("woob_applications.%s" % app)

        return getattr(app_module, app_module.__all__[0])

    @classmethod
    def run_app(cls, app, args):
        app_class = cls.load_app(app)
        return app_class.run([app] + args)

    @classmethod
    def print_list(cls, app_list):
        print('usage: woob [--version] <command> [<args>]')
        print()
        print('Use one of this commands:')
        for app in app_list:
            try:
                app_class = cls.load_app(app)
            except ImportError as e:
                print('   %-15s (unable to load: %s)' % (app, e))
            else:
                print('   %-15s %s' % (app_class.APPNAME, app_class.SHORT_DESCRIPTION))
        print()
        print('For more information about a command, use:')
        print('   $ man woob-<command>')
        print('or')
        print('   $ woob <command> --help')

    @classmethod
    def print_version(cls):
        print('%s v%s %s' % (woob.__name__, woob.__version__, woob.__copyright__))

    @classmethod
    def run(cls):
        if sys.version_info < (3, 7):
            print('woob requires python >= 3.7 to work', file=sys.stderr)
            return 1

        app_list = cls.list_apps()

        if len(sys.argv) < 2 or sys.argv[1] == '--help':
            return cls.print_list(app_list)

        if sys.argv[1] == '--version':
            return cls.print_version()

        if sys.argv[1] == 'update':
            sys.argv.insert(1, 'config')

        if sys.argv[1] not in app_list:
            print("woob: '{0}' is not a woob command. See 'woob --help'.".format(sys.argv[1]))
            words = difflib.get_close_matches(sys.argv[1], app_list)
            if words:
                print()
                print('The most similar command is\n\t{0}'.format('\n\t'.join(words)))
            return 1

        return cls.run_app(sys.argv[1], sys.argv[2:])
