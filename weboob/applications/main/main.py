#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Copyright(C) 2009-2017  Romain Bignon
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

import argparse
import importlib
import pkgutil

import woob.applications


def list_apps():
    apps = set()
    for module in pkgutil.iter_modules(woob.applications.__path__):
        apps.add(module.name)

    apps.remove("main")
    return sorted(apps)


def run_app(app, args):
    app_module = importlib.import_module("woob.applications.%s" % app)
    app_class = getattr(app_module, app_module.__all__[0])
    app_class.run([app] + args)


class WoobMain(object):
    @classmethod
    def run(cls):
        app_list = list_apps()

        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument("app", choices=app_list)
        args, rest = parser.parse_known_args()

        run_app(args.app, rest)
