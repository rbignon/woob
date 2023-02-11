# -*- coding: utf-8 -*-

# Copyright(C) 2012-2021  Budget Insight
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

from woob.capabilities.profile import CapProfile
from woob.capabilities.bank.wealth import CapBankWealth
from woob.tools.backend import Module, BackendConfig
from woob.tools.value import ValueBackendPassword, Value, ValueTransient

from .browser import SwisslifeBrowser


__all__ = ['SwisslifeModule']


class SwisslifeModule(Module, CapBankWealth, CapProfile):
    MODULE = 'swisslife'
    NAME = 'swisslife'
    DESCRIPTION = 'SwissLife'
    MAINTAINER = 'Christophe François'
    EMAIL = 'christophe.francois@budget-insight.com'
    LICENSE = 'LGPLv3+'
    VERSION = "3.2"
    CONFIG = BackendConfig(
        ValueBackendPassword('login', label='Identifiant personnel', masked=False),
        ValueBackendPassword('password', label='Mot de passe'),
        Value('domain', label='Domain', default='myswisslife.fr'),
        ValueTransient('captcha_response'),
        ValueTransient('sms'),
        ValueTransient('request_information'),
    )

    BROWSER = SwisslifeBrowser

    def create_default_browser(self):
        return self.create_browser(
            self.config,
            self.config['domain'].get(),
            self.config['login'].get(),
            self.config['password'].get(),
        )

    def iter_accounts(self):
        return self.browser.iter_accounts()

    def iter_history(self, account):
        return self.browser.iter_history(account)

    def iter_investment(self, account):
        return self.browser.iter_investment(account)

    def get_profile(self):
        return self.browser.get_profile()

    def iter_pocket(self, account):
        return self.browser.iter_pocket(account)
