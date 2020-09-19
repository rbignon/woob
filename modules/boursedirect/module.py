# -*- coding: utf-8 -*-

# Copyright(C) 2012-2020  Budget Insight
#
# This file is part of a weboob module.
#
# This weboob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This weboob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this weboob module. If not, see <http://www.gnu.org/licenses/>.

# flake8: compatible

from __future__ import unicode_literals

from weboob.tools.value import Value, ValueBackendPassword
from weboob.tools.backend import Module, BackendConfig
from weboob.capabilities.wealth import CapBankWealth

from .browser import BoursedirectBrowser


__all__ = ['BoursedirectModule']


class BoursedirectModule(Module, CapBankWealth):
    NAME = 'boursedirect'
    DESCRIPTION = 'Bourse direct'
    MAINTAINER = 'Vincent Ardisson'
    EMAIL = 'vardisson@budget-insight.com'
    LICENSE = 'LGPLv3+'
    VERSION = '2.1'

    BROWSER = BoursedirectBrowser

    CONFIG = BackendConfig(
        ValueBackendPassword('login', label='Identifiant', masked=False),
        ValueBackendPassword('password', label='Code personnel'),
        Value('otp', label='Code SMS', default='', required=False),
    )

    def create_default_browser(self):
        return self.create_browser(
            self.config['login'].get(),
            self.config['password'].get(),
        )

    def iter_accounts(self):
        return self.browser.iter_accounts()

    def iter_investment(self, account):
        return self.browser.iter_investment(account)

    def iter_market_orders(self, account):
        return self.browser.iter_market_orders(account)

    def iter_history(self, account):
        return self.browser.iter_history(account)
