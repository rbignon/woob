# -*- coding: utf-8 -*-

# Copyright(C) 2013 Romain Bignon
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
from woob.capabilities.bank import AccountNotFound
from woob.capabilities.bank.wealth import CapBankWealth
from woob.tools.backend import Module, BackendConfig
from woob.tools.value import ValueBackendPassword, Value

from .browser import CarrefourBanqueBrowser


__all__ = ['CarrefourBanqueModule']


class CarrefourBanqueModule(Module, CapBankWealth):
    NAME = 'carrefourbanque'
    MAINTAINER = 'Romain Bignon'
    EMAIL = 'romain@weboob.org'
    VERSION = '3.2'
    DESCRIPTION = 'Carrefour Banque'
    LICENSE = 'LGPLv3+'
    CONFIG = BackendConfig(
        ValueBackendPassword('login', label='Votre Identifiant Internet', masked=False),
        ValueBackendPassword('password', label="Code d'accès", regexp=r'\d+'),
        Value('captcha_response', label='Captcha Response', default='', required=False)
    )
    BROWSER = CarrefourBanqueBrowser

    def create_default_browser(self):
        return self.create_browser(self.config)

    def iter_accounts(self):
        return self.browser.get_account_list()

    def get_account(self, _id):
        return find_object(self.browser.get_account_list(), id=_id, error=AccountNotFound)

    def iter_history(self, account):
        return self.browser.iter_history(account)

    def iter_investment(self, account):
        return self.browser.iter_investment(account)
