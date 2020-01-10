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

from __future__ import unicode_literals

from datetime import datetime
from decimal import Decimal

from weboob.browser.pages import JsonPage, LoggedPage
from weboob.capabilities.bank import Account, Transaction, Rate
from weboob.tools.capabilities.bank.transactions import sorted_transactions
from weboob.capabilities.base import Currency
from weboob.exceptions import BrowserUnavailable


class ResponsePage(JsonPage):
    def on_load(self):
        error = self.get_error()
        if error and 'limit exceeded' in error:
            raise BrowserUnavailable(error)

    def get_error(self):
        error = self.doc.get('error', [])
        if len(error):
            return error[0]


class BalancePage(LoggedPage, ResponsePage):
    def iter_accounts(self):
        for currency, value in self.doc['result'].items():
            account = Account()
            account.id = currency
            account.type = Account.TYPE_CHECKING
            # Remove first symbol of the currency ('Z' or 'X')
            # except for 'DASH' & 'ATOM'
            if len(currency) == 4 and currency not in ('DASH', 'ATOM'):
                account.currency = account.label = currency[1:]
            else:
                account.currency = account.label = currency
            account.balance = Decimal(value)
            yield account


class HistoryPage(LoggedPage, ResponsePage):
    def get_tradehistory(self, currency):
        transactions_list = []
        all_transactions = (x for x in self.doc['result']['ledger'].values() if currency in x['asset'])
        for item in all_transactions:
            transaction = Transaction()
            transaction.type = Transaction.TYPE_TRANSFER
            transaction.id = item['refid']
            transaction.amount = Decimal(item['amount'])
            transaction.date = datetime.fromtimestamp(item['time'])
            transaction.raw = item['type']
            transaction.commission = Decimal(item['fee'])
            transactions_list.append(transaction)

        return(sorted_transactions(transactions_list))


class AssetsPage(LoggedPage, ResponsePage):
    def iter_currencies(self):
        assets = self.doc['result']
        for asset in assets:
            currency = Currency()
            currency.id = self.doc['result'][asset]['altname']
            yield currency


class AssetPairsPage(LoggedPage, ResponsePage):
    def get_asset_pairs(self):
        r = self.doc['result']
        pair_list = []
        for item in r:
            # cut parasite characters where it's necessary
            if item.endswith('.d'):
                item = item[:-2]
            pair_list.append(item)
        return pair_list


class TickerPage(LoggedPage, ResponsePage):
    def get_rate(self):
        rate = Rate()
        rate.datetime = datetime.now()
        rate.value = Decimal(str(list(self.doc['result'].values())[0]['c'][0]))
        return rate


class TradePage(LoggedPage, JsonPage):
    def get_error(self):
        return self.doc['error']
