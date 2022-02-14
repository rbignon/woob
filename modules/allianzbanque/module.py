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

# flake8: compatible

from woob.capabilities.profile import CapProfile
from woob.capabilities.bank.wealth import CapBankWealth
from woob.tools.backend import AbstractModule, BackendConfig
from woob.tools.value import ValueBackendPassword, ValueTransient

from .browser import AllianzbanqueBrowser


__all__ = ['AllianzbanqueModule']


class AllianzbanqueModule(AbstractModule, CapBankWealth, CapProfile):
    NAME = 'allianzbanque'
    DESCRIPTION = 'Allianz Banque'
    MAINTAINER = 'Damien Mat'
    EMAIL = 'damien.mat@budget-insight.com'
    LICENSE = 'LGPLv3+'
    VERSION = '3.1'
    BROWSER = AllianzbanqueBrowser
    PARENT = 'cmso'

    CONFIG = BackendConfig(
        ValueBackendPassword('login', label='Identifiant', masked=False),
        ValueBackendPassword('password', label='Mot de passe'),
        ValueTransient('code'),
        ValueTransient('request_information'),
    )

    def create_default_browser(self):
        return self.create_browser(
            self.config,
            self.config['login'].get(),
            self.config['password'].get(),
            weboob=self.weboob
        )

    def iter_investment(self, account):
        # not using CMSO CapBankWealth
        return self.browser.iter_investment(account)

    def iter_market_orders(self, account):
        # not using CMSO CapBankWealth
        raise NotImplementedError()

    def init_transfer(self, transfer, **params):
        # not using CMSO CapBankTransfer
        raise NotImplementedError()

    def iter_transfer_recipients(self, origin_account):
        # not using CMSO CapBankTransfer
        raise NotImplementedError()

    def iter_emitters(self):
        # not using CMSO CapBankTransfer
        raise NotImplementedError()
