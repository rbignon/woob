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

from woob.capabilities.bank import (
    Account,
    AccountNotFound,
    CapBankTransferAddRecipient,
    RecipientNotFound,
    TransferInvalidLabel,
)
from woob.capabilities.bank.wealth import CapBankWealth
from woob.capabilities.base import find_object, find_object_any_match
from woob.capabilities.profile import CapProfile
from woob.tools.backend import BackendConfig, Module
from woob.tools.value import ValueBackendPassword, ValueTransient

from .browser import FortuneoBrowser


__all__ = ["FortuneoModule"]


class FortuneoModule(Module, CapBankWealth, CapBankTransferAddRecipient, CapProfile):
    NAME = "fortuneo"
    MAINTAINER = "Gilles-Alexandre Quenot"
    EMAIL = "gilles.quenot@gmail.com"
    VERSION = "3.7"
    LICENSE = "LGPLv3+"
    DESCRIPTION = "Fortuneo"
    CONFIG = BackendConfig(
        ValueBackendPassword("login", label="Identifiant", masked=False, required=True),
        ValueBackendPassword("password", label="Mot de passe", required=True),
        ValueTransient("code"),
        ValueTransient("request_information"),
    )
    BROWSER = FortuneoBrowser

    def create_default_browser(self):
        return self.create_browser(
            self.config,
            self.config["login"].get(),
            self.config["password"].get(),
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
            account_id = origin_account.id
            account_iban = origin_account.iban
        else:
            account_id = origin_account
            account_iban = None
        account = self.find_account_for_transfer(account_id, account_iban, account_list, False)

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

    def find_account_for_transfer(self, account_id, account_iban, accounts=None, raise_not_found=True):
        if not (account_id or account_iban):
            raise ValueError("You must at least provide an account ID or IBAN")

        if not accounts:
            accounts = list(self.iter_accounts())

        # Basic find object - try 1
        account = find_object_any_match(accounts, (("id", account_id), ("iban", account_iban)))

        # fallback search with a trick - try 2
        if not account and account_iban:
            for other_account in accounts:
                # Example
                # If account IBAN is FRXXXXXXXXXXXXXX123456789XX
                # Account number will be N°XXX123456789
                # XXX TODO : check account type with this technique
                if other_account.number[3:] == account_iban[16:25]:
                    account = other_account

        # There is a chance that the account has no IBAN because it's not loaded if no SCA has
        # been triggered
        if account and not account.iban:
            account.iban = account_iban

        if not account and raise_not_found:
            raise AccountNotFound()
        return account

    def transfer_check_account_id(self, original_value, new_value):
        # The account ID can change if a transfer is initiated with an account identified by its ID
        # Also we already check that the data wasn't changed during the handle_response before
        # validating the transfer
        return True

    def init_transfer(self, transfer, **params):
        if "code" in params:
            return transfer

        if not transfer.label:
            raise TransferInvalidLabel()

        self.logger.info("Going to do a new transfer")
        account = self.find_account_for_transfer(transfer.account_id, transfer.account_iban)
        recipient = find_object_any_match(
            self.iter_transfer_recipients(account),
            (("id", transfer.recipient_id), ("iban", transfer.recipient_iban)),
            error=RecipientNotFound,
        )
        return self.browser.init_transfer(account, recipient, transfer.amount, transfer.label, transfer.exec_date)

    def execute_transfer(self, transfer, **params):
        return self.browser.execute_transfer(transfer, **params)

    def iter_emitters(self):
        return self.browser.iter_emitters()

    def iter_transfers(self, account=None):
        if account and not isinstance(account, Account):
            account = self.get_account(account)
        return self.browser.iter_transfers(account)
