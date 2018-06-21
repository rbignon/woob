# -*- coding: utf-8 -*-

# Copyright(C) 2012-2022  Budget Insight
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

from __future__ import unicode_literals


from weboob.tools.backend import Module, BackendConfig
from weboob.capabilities.bank import CapBank
from weboob.tools.value import ValueBackendPassword, Value

from .browser import KrakenBrowser


__all__ = ['KrakenModule']


class KrakenModule(Module, CapBank):
    NAME = 'kraken'
    DESCRIPTION = 'Kraken bitcoin exchange'
    MAINTAINER = 'Andras Bartok'
    EMAIL = 'andras.bartok@budget-insight.com'
    LICENSE = 'LGPLv3+'
    VERSION = '1.4'

    BROWSER = KrakenBrowser

    CONFIG = BackendConfig(ValueBackendPassword('username', label='Username', masked=False),
                           ValueBackendPassword('password', label='Password', masked=True),
                           ValueBackendPassword('otp', label='Two factor auth password (if enabled)', masked=True, required=False, default=''),
                           Value('captcha_response', label='Captcha Response', default='', required=False),
                           Value('key_name', label='API key name', default='Budgea'))

    def create_default_browser(self):
        return self.create_browser(self.config)

    def iter_accounts(self):
        return self.browser.iter_accounts()

    def iter_history(self, account):
        return self.browser.iter_history(account.currency)
