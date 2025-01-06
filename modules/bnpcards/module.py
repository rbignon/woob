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

from woob.tools.backend import Module, BackendConfig
from woob.capabilities.bank import CapBank, AccountNotFound
from woob.capabilities.base import find_object
from woob.tools.value import ValueBackendPassword, Value

from .proxy_browser import ProxyBrowser


__all__ = ['BnpcartesentrepriseModule']


class BnpcartesentrepriseModule(Module, CapBank):
    NAME = 'bnpcards'
    DESCRIPTION = 'BNP Cartes Entreprises'
    MAINTAINER = 'Baptiste Delpey'
    EMAIL = 'bdelpey@budget-insight.fr'
    LICENSE = 'LGPLv3+'
    VERSION = '3.7'
    CONFIG = BackendConfig(
        ValueBackendPassword('login', label='Identifiant', masked=False),
        ValueBackendPassword('password', label='Code personnel'),
        Value(
            'type',
            label='Profil de connexion',
            default='1',
            choices={
                '1': 'Titulaire',
                '2': 'Gestionnaire',
            }
        )
    )

    BROWSER = ProxyBrowser

    def create_default_browser(self):
        return self.create_browser(self.config['type'].get(),
                                   self.config['login'].get(),
                                   self.config['password'].get())

    def get_account(self, _id):
        return find_object(self.browser.iter_accounts(), id=_id, error=AccountNotFound)

    def iter_accounts(self):
        for acc in self.browser.iter_accounts():
            acc._bisoftcap = {'all': {'softcap_day':5,'day_for_softcap':100}}
            yield acc
        # If this browser exists we have corporate cards, that we also need to fetch
        if self.browser.corporate_browser:
            for acc in self.browser.corporate_browser.iter_accounts():
                acc._bisoftcap = {'all': {'softcap_day': 5, 'day_for_softcap': 100}}
                yield acc

    def iter_history(self, account):
        if getattr(account, '_is_corporate', False):
            get_transactions = self.browser.corporate_browser.get_transactions
        else:
            get_transactions = self.browser.get_transactions

        for tr in get_transactions(account):
            if not tr.coming:
                yield tr

    def iter_coming(self, account):
        if getattr(account, '_is_corporate', False):
            get_transactions = self.browser.corporate_browser.get_transactions
        else:
            get_transactions = self.browser.get_transactions

        for tr in get_transactions(account):
            if not tr.coming:
                break
            yield tr
