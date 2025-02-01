# -*- coding: utf-8 -*-

# Copyright(C) 2019      Antoine BOSSY
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

from woob.capabilities.bill import CapDocument
from woob.tools.backend import BackendConfig, Module
from woob.tools.value import Value, ValueBackendPassword

from .browser import TicketCesuBrowser


__all__ = ["TicketsCesuModule"]


class TicketsCesuModule(Module, CapDocument):
    """Almost empty module at the moment: not tested in the wild.

    CapBank methods were written from a previous version of the module, but not tested and not in any present use case.
    –> CapBank not implemented.
    CapDocument methods are not written but are to be done once connections are made
    –> CapDocument methods to be implemented
    """

    NAME = "ticketscesu"
    DESCRIPTION = "Tickets CESU Edenred"
    MAINTAINER = "Antoine BOSSY"
    EMAIL = "mail+github@abossy.fr"
    LICENSE = "LGPLv3+"
    VERSION = "3.7"

    BROWSER = TicketCesuBrowser

    CONFIG = BackendConfig(
        Value("login", label="Identifiant", masked=False),
        ValueBackendPassword("password", label="Code secret", required=True),
    )

    def create_default_browser(self):
        return self.create_browser(self.config["login"].get(), self.config["password"].get())

    def iter_accounts(self):
        return self.browser.iter_accounts()

    def iter_history(self, account):
        return self.browser.iter_history(account.id)

    def iter_subscription(self):
        return self.browser.iter_subscription()
