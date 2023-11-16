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

from woob.tools.backend import Module, BackendConfig
from woob.capabilities.bank import (
    CapCurrencyRate, CapBankTransferAddRecipient, Account, AccountNotFound,
    RecipientNotFound,
)
from woob.capabilities.base import find_object
from woob.tools.value import ValueBackendPassword, ValueTransient, ValueBool

from .browser import KrakenBrowser


__all__ = ['KrakenModule']


class KrakenModule(Module, CapBankTransferAddRecipient, CapCurrencyRate):
    NAME = 'kraken'
    DESCRIPTION = 'Kraken bitcoin exchange'
    MAINTAINER = 'Andras Bartok'
    EMAIL = 'andras.bartok@budget-insight.com'
    LICENSE = 'LGPLv3+'
    VERSION = '3.6'

    BROWSER = KrakenBrowser

    CONFIG = BackendConfig(
        ValueBackendPassword('api_key', label='API key'),
        ValueBackendPassword('private_api_key', label='Private API key'),
        ValueBool('otp_enabled', label='Two factor auth password enabled (on API keys)', choices={'y': 'Enabled', 'n': 'Disabled'}),
        ValueTransient('otp'),
        ValueTransient('request_information'),
    )

    # kraken uses XBT instead of BTC, but we want to keep BTC in the responses
    def convert_id(self, currency_id):
        return {'BTC':'XBT','XBT':'BTC'}.get(currency_id, currency_id)

    def create_default_browser(self):
        return self.create_browser(self.config)

    def iter_accounts(self):
        for account in self.browser.iter_accounts():
            account.label = account.currency = self.convert_id(account.currency)
            yield account

    def iter_history(self, account):
        return self.browser.iter_history(self.convert_id(account.currency))

    def iter_transfer_recipients(self, account):
        if not isinstance(account, Account):
            account = self.get_account(account)
        return self.browser.iter_recipients(account)

    def init_transfer(self, transfer, **params):
        return transfer

    def execute_transfer(self, transfer, **params):
        account = find_object(self.iter_accounts(), id=transfer.account_id, error=AccountNotFound)
        recipient = find_object(self.iter_transfer_recipients(account), id=transfer.recipient_id, error=RecipientNotFound)
        return self.browser.execute_transfer(account, recipient, transfer)

    def iter_currencies(self):
        for currency in self.browser.iter_currencies():
            currency.id = self.convert_id(currency.id)
            yield currency

    def get_rate(self, currency_from, currency_to):
        rate = self.browser.get_rate(self.convert_id(currency_from), self.convert_id(currency_to))
        if rate:
            rate.currency_from = currency_from
            rate.currency_to = currency_to
        return rate
