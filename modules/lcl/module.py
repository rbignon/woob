# -*- coding: utf-8 -*-

# Copyright(C) 2010-2013  Romain Bignon, Pierre Mazière
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

from woob.capabilities.bank import Account
from woob.capabilities.bank.pfm import CapBankMatching
from woob.capabilities.bank.wealth import CapBankWealth
from woob.exceptions import NotImplementedWebsite
from woob.tools.backend import Module, BackendConfig
from woob.tools.value import Value, ValueBackendPassword, ValueTransient

from .browser import LCLBrowser


__all__ = ['LCLModule']


class LCLModule(Module, CapBankWealth, CapBankMatching):
    NAME = 'lcl'
    MAINTAINER = u'Romain Bignon'
    EMAIL = 'romain@weboob.org'
    VERSION = '3.6'
    DESCRIPTION = u'LCL'
    LICENSE = 'LGPLv3+'
    CONFIG = BackendConfig(
        ValueBackendPassword('login', label='Identifiant', masked=False, regexp=r'\d{10}'),
        ValueBackendPassword('password', label='Code personnel', regexp=r'\d{6}'),
        Value(
            'website',
            label='Type de compte',
            default='par',
            choices={
                'par': 'Particuliers',
                'pro': 'Professionnels',
                'ent': 'Entreprises',
                'esp': 'Espace Pro',
            },
            aliases={'elcl': 'par'}
        ),
        ValueTransient('resume'),
        ValueTransient('request_information'),
        ValueTransient('code', regexp=r'^\d{6}$'),
    )
    BROWSER = LCLBrowser

    def create_default_browser(self):
        if self.config['website'].get() == 'cards':
            # 'cards' is not covered by this API.
            self.logger.info('A connection using the cards website is found.')
            raise NotImplementedWebsite()

        return self.create_browser(
            self.config['login'].get(),
            self.config['password'].get()
        )

    def iter_accounts(self):
        return self.browser.iter_accounts()

    def iter_coming(self, account):
        return self.browser.iter_coming(account)

    def iter_history(self, account):
        return self.browser.iter_history(account)

    def iter_investment(self, account):
        return self.browser.iter_investment(account)

    def match_account(self, account, previous_accounts):
        # Ids of cards are not consistent with other LCL sources.
        # Try matching on card number and coming amount.

        if account.type != Account.TYPE_CARD:
            return None

        matched_accounts = []
        for previous_account in previous_accounts:
            if (
                previous_account.type == Account.TYPE_CARD
                and previous_account.number == account.number
                and previous_account.coming == account.coming
            ):
                matched_accounts.append(previous_account)
                if len(matched_accounts) > 1:
                    raise AssertionError(f'Found multiple candidates to match the card {account.label}.')

        if matched_accounts:
            self.logger.info(
                "Matched new account '%s' with previous account '%s' from matching_account",
                account,
                matched_accounts[0]
            )
            return matched_accounts[0]

        # explicit return if no match found
        return None
