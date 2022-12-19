# -*- coding: utf-8 -*-

# Copyright(C) 2016      Edouard Lambert
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


from woob.capabilities.bank import AccountNotFound
from woob.capabilities.bank.wealth import CapBankWealth
from woob.capabilities.base import find_object
from woob_modules.cmes.module import CmesModule

from .browser import CmesBrowser


__all__ = ['CicesModule']


class CicesModule(CmesModule, CapBankWealth):
    NAME = 'cices'
    DESCRIPTION = u'CIC Épargne Salariale'
    MAINTAINER = u'Edouard Lambert'
    EMAIL = 'elambert@budget-insight.com'
    LICENSE = 'LGPLv3+'
    VERSION = '3.1'
    DEPENDENCIES = ('cmes',)

    BROWSER = CmesBrowser

    def create_default_browser(self):
        return self.create_browser(
            self.config,
            self.config['login'].get(),
            self.config['password'].get(),
            'https://www.cic-epargnesalariale.fr',
            woob=self.woob
        )

    def get_account(self, _id):
        return find_object(self.browser.iter_accounts(), id=_id, error=AccountNotFound)

    def iter_accounts(self):
        return self.browser.iter_accounts()

    def iter_history(self, account):
        return self.browser.iter_history(account)

    def iter_investment(self, account):
        return self.browser.iter_investment(account)

    def iter_pocket(self, account):
        return self.browser.iter_pocket(account)
