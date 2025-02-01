# -*- coding: utf-8 -*-

# Copyright(C) 2020      Vincent A
#
# This file is part of a woob module.
#
# This woob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This woob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this woob module. If not, see <http://www.gnu.org/licenses/>.

# flake8: compatible

from woob.capabilities.base import find_object
from woob.capabilities.messages import CapMessages, Thread
from woob.tools.backend import BackendConfig, Module
from woob.tools.value import ValueBackendPassword

from .browser import DonnonsBrowser


__all__ = ["DonnonsModule"]


class DonnonsModule(Module, CapMessages):
    NAME = "donnons"
    DESCRIPTION = "donnons website"
    MAINTAINER = "Vincent A"
    EMAIL = "dev@indigo.re"
    LICENSE = "LGPLv3+"
    VERSION = "3.7"

    CONFIG = BackendConfig(
        ValueBackendPassword("login", label="Email", masked=False),
        ValueBackendPassword("password", label="Mot de passe"),
    )

    BROWSER = DonnonsBrowser

    def create_default_browser(self):
        return self.create_browser(self.config["login"].get(), self.config["password"].get())

    def iter_threads(self):
        return self.browser.iter_threads()

    def get_thread(self, id):
        return find_object(self.iter_threads(), id=id)

    def fill_thread(self, thread, fields):
        if "root" in fields:
            self.browser.fill_thread(thread)

    OBJECTS = {
        Thread: fill_thread,
    }
