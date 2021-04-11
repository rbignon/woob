# -*- coding: utf-8 -*-

# Copyright(C) 2012-2014 Romain Bignon
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

from __future__ import unicode_literals

import re

from woob.capabilities.bank import (
    AccountNotFound, Account, CapBankTransferAddRecipient,
    RecipientInvalidLabel, TransferInvalidLabel, RecipientNotFound,
)
from woob.capabilities.wealth import CapBankWealth
from woob.capabilities.base import find_object
from woob.capabilities.profile import CapProfile
from woob.tools.backend import Module, BackendConfig
from woob.tools.value import ValueBackendPassword, Value, ValueTransient

from .bred import BredBrowser
from .dispobank import DispoBankBrowser


__all__ = ['BredModule']


class BredModule(Module, CapBankWealth, CapProfile, CapBankTransferAddRecipient):
    NAME = 'bred'
    MAINTAINER = 'Romain Bignon'
    EMAIL = 'romain@weboob.org'
    VERSION = '3.0'
    DESCRIPTION = u'Bred'
    LICENSE = 'LGPLv3+'
    CONFIG = BackendConfig(
        ValueBackendPassword('login', label='Identifiant', masked=False, regexp=r'.{,32}'),
        ValueBackendPassword('password', label='Mot de passe'),
        Value('website', label="Site d'accès", default='bred',
              choices={'bred': 'BRED', 'dispobank': 'DispoBank'}),
        Value('accnum', label='Numéro du compte bancaire (optionnel)', default='', masked=False),
        ValueTransient('request_information'),
        ValueTransient('resume'),
        ValueTransient('otp_sms'),
        ValueTransient('otp_app'),
    )

    BROWSERS = {
        'bred': BredBrowser,
        'dispobank': DispoBankBrowser,
    }

    def get_website(self):
        return self.config['website'].get()

    def create_default_browser(self):
        self.BROWSER = self.BROWSERS[self.get_website()]

        return self.create_browser(
            self.config['accnum'].get().replace(' ', '').zfill(11),
            self.config,
            weboob=self.weboob,
        )

    def iter_accounts(self):
        return self.browser.get_accounts_list()

    def get_account(self, _id):
        return find_object(self.browser.get_accounts_list(), id=_id, error=AccountNotFound)

    def iter_history(self, account):
        return self.browser.get_history(account)

    def iter_coming(self, account):
        return self.browser.get_history(account, coming=True)

    def iter_investment(self, account):
        return self.browser.iter_investments(account)

    def iter_market_orders(self, account):
        return self.browser.iter_market_orders(account)

    def get_profile(self):
        return self.browser.get_profile()

    def fill_account(self, account, fields):
        if self.get_website() != 'bred':
            return

        self.browser.fill_account(account, fields)

    OBJECTS = {
        Account: fill_account,
    }

    def iter_transfer_recipients(self, account):
        if self.get_website() != 'bred':
            raise NotImplementedError()

        if not isinstance(account, Account):
            account = find_object(self.iter_accounts(), id=account)

        return self.browser.iter_transfer_recipients(account)

    def new_recipient(self, recipient, **params):
        if self.get_website() != 'bred':
            raise NotImplementedError()

        recipient.label = recipient.label[:32].strip()

        regex = r'[-a-z0-9A-Z ,.]+'
        if not re.match(r'(?:%s)\Z' % regex, recipient.label, re.UNICODE):
            invalid_chars = re.sub(regex, '', recipient.label, flags=re.UNICODE)
            raise RecipientInvalidLabel('Le nom du bénéficiaire contient des caractères non autorisés : "%s"' % invalid_chars)

        return self.browser.new_recipient(recipient, **params)

    def init_transfer(self, transfer, **params):
        if self.get_website() != 'bred':
            raise NotImplementedError()

        transfer.label = transfer.label[:140].strip()

        regex = r'[-a-z0-9A-Z ,.]+'
        if not re.match(r'(?:%s)\Z' % regex, transfer.label, re.UNICODE):
            invalid_chars = re.sub(regex, '', transfer.label, flags=re.UNICODE)
            # Remove duplicate characters to avoid displaying them multiple times
            invalid_chars = ''.join(set(invalid_chars))
            raise TransferInvalidLabel('Le libellé du transfert contient des caractères non autorisés : "%s"' % invalid_chars)

        account = find_object(self.iter_accounts(), id=transfer.account_id, error=AccountNotFound)

        if transfer.recipient_iban:
            recipient = find_object(self.iter_transfer_recipients(account), iban=transfer.recipient_iban, error=RecipientNotFound)
        else:
            recipient = find_object(self.iter_transfer_recipients(account), id=transfer.recipient_id, error=RecipientNotFound)

        return self.browser.init_transfer(transfer, account, recipient, **params)

    def execute_transfer(self, transfer, **params):
        if self.get_website() != 'bred':
            raise NotImplementedError()
        return self.browser.execute_transfer(transfer, **params)
