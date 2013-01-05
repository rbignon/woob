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


from weboob.capabilities.bank import CapBank, AccountNotFound
from weboob.tools.backend import Module, BackendConfig
from weboob.tools.value import ValueBackendPassword

from .browser import CreditDuNordBrowser


__all__ = ['CreditDuNordModule']


class CreditDuNordModule(Module, CapBank):
    NAME = 'courtois'
    MAINTAINER = u'Romain Bignon'
    EMAIL = 'romain@weboob.org'
    VERSION = '1.4'
    DESCRIPTION = u'Banque Courtois'
    LICENSE = 'LGPLv3+'
    CONFIG = BackendConfig(ValueBackendPassword('login',    label='Identifiant', masked=False),
                           ValueBackendPassword('password', label='Code confidentiel'))
    BROWSER = CreditDuNordBrowser

    def create_default_browser(self):
        return self.create_browser(self.weboob, 'www.banque-courtois.fr', self.config['login'].get(), self.config['password'].get())

    def iter_accounts(self):
        for account in self.browser.get_accounts_list():
            account._bisoftcap = {'cb': {'softcap_day':50,'day_for_softcap':25}, 'deferred_cb': {'softcap_day':50,'day_for_softcap':25}}
            yield account

    def get_account(self, _id):
        account = self.browser.get_account(_id)
        if account:
            return account
        else:
            raise AccountNotFound()

    def iter_history(self, account):
        account = self.browser.get_account(account.id)
        for tr in self.browser.get_history(account):
            if not tr._is_coming:
                yield tr

    def iter_coming(self, account):
        account = self.browser.get_account(account.id)
        for tr in self.browser.get_history(account, coming=True):
            if tr._is_coming:
                yield tr

    def iter_investment(self, account):
        account = self.browser.get_account(account.id)
        return self.browser.get_investment(account)
