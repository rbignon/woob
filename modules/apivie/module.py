# -*- coding: utf-8 -*-

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

from __future__ import unicode_literals

from woob.capabilities.bank.wealth import CapBankWealth
from woob.tools.backend import Module, BackendConfig
from woob.tools.value import ValueBackendPassword

from .browser import ApivieBrowser


__all__ = ['ApivieModule']


class ApivieModule(Module, CapBankWealth):
    NAME = 'apivie'
    DESCRIPTION = 'Apivie'
    MAINTAINER = 'Romain Bignon'
    EMAIL = 'romain@weboob.org'
    VERSION = '3.1'

    BROWSER = ApivieBrowser

    CONFIG = BackendConfig(
        ValueBackendPassword('login', label='Identifiant', masked=False),
        ValueBackendPassword('password', label='Mot de passe')
    )

    def create_default_browser(self):
        return self.create_browser(
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
