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


from __future__ import unicode_literals

import re
from decimal import Decimal

from weboob.capabilities.bank import (
    CapBankWealth, CapBankTransferAddRecipient, AccountNotFound, Account, RecipientNotFound,
    TransferInvalidLabel,
)
from weboob.capabilities.profile import CapProfile
from weboob.capabilities.base import find_object
from weboob.tools.backend import Module, BackendConfig
from weboob.tools.value import ValueBackendPassword

from .browser import HelloBank


__all__ = ['HelloBankModule']


class HelloBankModule(Module, CapBankWealth, CapBankTransferAddRecipient, CapProfile):
    NAME = 'hellobank'
    MAINTAINER = u'Romain Bignon'
    EMAIL = 'romain@weboob.org'
    VERSION = '1.1'
    LICENSE = 'AGPLv3+'
    DESCRIPTION = 'BNP Paribas'
    CONFIG = BackendConfig(
        ValueBackendPassword('login',      label=u'Numéro client', masked=False),
        ValueBackendPassword('password',   label=u'Code secret', regexp='^(\d{6})$'))
    BROWSER = HelloBank

    def create_default_browser(self):
        return self.create_browser(self.config, weboob=self.weboob)

    def iter_accounts(self):
        return self.browser.get_accounts_list()

    def get_account(self, _id):
        account = self.browser.get_account(_id)
        if account:
            return account
        else:
            raise AccountNotFound()

    def iter_history(self, account):
        return self.browser.iter_history(account)

    def iter_coming(self, account):
        return self.browser.iter_coming_operations(account)

    def iter_investment(self, account):
        return self.browser.iter_investment(account)

    def iter_transfer_recipients(self, origin_account):
        if isinstance(origin_account, Account):
            origin_account = origin_account.id
        return self.browser.iter_recipients(origin_account)

    def new_recipient(self, recipient, **params):
        # Recipient label has max 70 chars.
        recipient.label = ' '.join(w for w in re.sub('[^0-9a-zA-Z-,\.: ]+', '', recipient.label).split())[:70]
        return self.browser.new_recipient(recipient, **params)

    def init_transfer(self, transfer, **params):
        if transfer.label is None:
            raise TransferInvalidLabel()

        self.logger.info('Going to do a new transfer')
        if transfer.account_iban:
            account = find_object(self.iter_accounts(), iban=transfer.account_iban, error=AccountNotFound)
        else:
            account = find_object(self.iter_accounts(), id=transfer.account_id, error=AccountNotFound)

        recipient = find_object(self.iter_transfer_recipients(account.id), id=transfer.recipient_id, error=RecipientNotFound)

        assert account.id.isdigit()
        # quantize to show 2 decimals.
        amount = Decimal(transfer.amount).quantize(Decimal(10) ** -2)

        return self.browser.init_transfer(account, recipient, amount, transfer.label, transfer.exec_date)

    def execute_transfer(self, transfer, **params):
        return self.browser.execute_transfer(transfer)

    def get_profile(self):
        return self.browser.get_profile()
