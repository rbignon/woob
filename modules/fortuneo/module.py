# -*- coding: utf-8 -*-

# Copyright(C) 2012 Gilles-Alexandre Quenot
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

from weboob.capabilities.base import find_object
from weboob.capabilities.bank import (
    CapBankTransferAddRecipient, AccountNotFound, RecipientNotFound,
    TransferInvalidLabel, Account,
)
from weboob.capabilities.wealth import CapBankWealth
from weboob.capabilities.profile import CapProfile
from weboob.tools.backend import Module, BackendConfig
from weboob.tools.value import ValueBackendPassword, ValueTransient

from .browser import FortuneoBrowser


__all__ = ['FortuneoModule']


class FortuneoModule(Module, CapBankWealth, CapBankTransferAddRecipient, CapProfile):
    NAME = 'fortuneo'
    MAINTAINER = u'Gilles-Alexandre Quenot'
    EMAIL = 'gilles.quenot@gmail.com'
    VERSION = '2.1'
    LICENSE = 'LGPLv3+'
    DESCRIPTION = u'Fortuneo'
    CONFIG = BackendConfig(
        ValueBackendPassword('login', label='Identifiant', masked=False, required=True),
        ValueBackendPassword('password', label='Mot de passe', required=True),
        ValueTransient('code'),
        ValueTransient('request_information')
    )
    BROWSER = FortuneoBrowser

    def create_default_browser(self):
        return self.create_browser(
            self.config,
            self.config['login'].get(),
            self.config['password'].get(),
            weboob=self.weboob
        )

    def iter_accounts(self):
        for account in self.browser.iter_accounts():
            yield account

    def iter_history(self, account):
        """Iter history of transactions on a specific account"""
        return self.browser.iter_history(account)

    def iter_coming(self, account):
        return self.browser.iter_coming(account)

    def iter_investment(self, account):
        return self.browser.iter_investments(account)

    def iter_market_orders(self, account):
        return self.browser.iter_market_orders(account)

    def get_profile(self):
        return self.browser.get_profile()

    def iter_transfer_recipients(self, origin_account):
        account_list = list(self.iter_accounts())

        if isinstance(origin_account, Account):
            account = find_object(account_list, id=origin_account.id)
        else:
            account = find_object(account_list, id=origin_account)

        if not account:
            # TPP can use _tpp_id for matching accounts
            if isinstance(origin_account, Account):
                account = find_object(account_list, _tpp_id=origin_account.id)
            else:
                account = find_object(account_list, _tpp_id=origin_account)

        if not account:
            raise AccountNotFound()

        return self.browser.iter_recipients(account)

    def new_recipient(self, recipient, **params):
        recipient.label = recipient.label[:35].upper()
        return self.browser.new_recipient(recipient, **params)

    def init_transfer(self, transfer, **params):
        if not transfer.label:
            raise TransferInvalidLabel()

        self.logger.info('Going to do a new transfer')
        account = find_object(self.iter_accounts(), id=transfer.account_id, error=AccountNotFound)

        if transfer.recipient_iban:
            recipient = find_object(
                self.iter_transfer_recipients(account.id),
                iban=transfer.recipient_iban,
                error=RecipientNotFound
            )
        else:
            recipient = find_object(
                self.iter_transfer_recipients(account.id),
                id=transfer.recipient_id,
                error=RecipientNotFound
            )

        return self.browser.init_transfer(account, recipient, transfer.amount, transfer.label, transfer.exec_date)

    def execute_transfer(self, transfer, **params):
        return self.browser.execute_transfer(transfer)

    def iter_emitters(self):
        return self.browser.iter_emitters()

    def iter_transfers(self, account=None):
        if account and not isinstance(account, Account):
            account = self.get_account(account)
        return self.browser.iter_transfers(account)
