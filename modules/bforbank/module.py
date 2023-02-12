# -*- coding: utf-8 -*-

# Copyright(C) 2015      Baptiste Delpey
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

from woob.tools.backend import Module, BackendConfig
from woob.capabilities.bank import AccountNotFound
from woob.capabilities.bank.wealth import CapBankWealth
from woob.capabilities.base import find_object
from woob.capabilities.profile import CapProfile
from woob.tools.value import ValueBackendPassword, ValueDate, ValueTransient

from .browser import BforbankBrowser


__all__ = ['BforbankModule']


class BforbankModule(Module, CapBankWealth, CapProfile):
    NAME = 'bforbank'
    DESCRIPTION = u'BforBank'
    MAINTAINER = u'Baptiste Delpey'
    EMAIL = 'b.delpey@hotmail.fr'
    LICENSE = 'LGPLv3+'
    VERSION = '3.3.1'
    DEPENDENCIES = ('lcl', 'spirica')
    CONFIG = BackendConfig(
        ValueBackendPassword('login', label='Identifiant', masked=False),
        ValueBackendPassword('password', label='Code personnel', regexp=r'\d+$'),
        ValueDate('birthdate', label='Date de naissance', formats=('%d/%m/%Y',)),
        ValueTransient('code', regexp=r'\d{6}'),
        ValueTransient('request_information'),
    )

    BROWSER = BforbankBrowser

    def create_default_browser(self):
        return self.create_browser(self.config, woob=self.woob)

    def get_account(self, _id):
        return find_object(self.browser.iter_accounts(), id=_id, error=AccountNotFound)

    def iter_accounts(self):
        return self.browser.iter_accounts()

    def iter_coming(self, account):
        return self.browser.get_coming(account)

    def iter_history(self, account):
        return self.browser.get_history(account)

    def iter_investment(self, account):
        return self.browser.iter_investment(account)

    def get_profile(self):
        return self.browser.get_profile()
