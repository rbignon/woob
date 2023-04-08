# Copyright(C) 2013      Romain Bignon
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

from woob.capabilities.bank.wealth import CapBankWealth
from woob.tools.backend import Module, BackendConfig
from woob.tools.value import ValueBackendPassword, ValueTransient

from .browser import ApivieBrowser


__all__ = ['ApivieModule']


class ApivieModule(Module, CapBankWealth):
    NAME = 'apivie'
    DESCRIPTION = 'Apivie'
    MAINTAINER = 'Romain Bignon'
    EMAIL = 'romain@weboob.org'
    VERSION = '3.5'

    BROWSER = ApivieBrowser

    CONFIG = BackendConfig(
        ValueBackendPassword('login', label='Identifiant', masked=False),
        ValueBackendPassword('password', label='Mot de passe'),
        ValueTransient('request_information'),
        ValueTransient('otp_sms'),
    )

    def create_default_browser(self):
        return self.create_browser(
            self.config,
            'hub.apivie.fr',
            self.config['login'].get(),
            self.config['password'].get()
        )

    def iter_accounts(self):
        return self.browser.iter_accounts()

    def iter_investment(self, account):
        return self.browser.iter_investment(account)

    def iter_history(self, account):
        return self.browser.iter_history(account)
