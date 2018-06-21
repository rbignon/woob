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

import json
from datetime import date
from decimal import Decimal

from weboob.browser.pages import JsonPage, HTMLPage
from weboob.capabilities.bank import Account, Transaction
from weboob.browser.filters.html import Attr
from weboob.tools.capabilities.bank.transactions import sorted_transactions
from weboob.browser.filters.standard import CleanText
from weboob.capabilities.base import NotAvailable


class LoginPage(HTMLPage):
    def login(self, username, password, otp, captcha_response=None):
        form = self.get_form()
        form['username'] = username
        form['password'] = password
        form['otp'] = otp
        if captcha_response:
            form['g-recaptcha-response'] = captcha_response
        form.submit()

    def get_error(self):
        return CleanText('//div[@class="alert alert-danger"]')(self.doc)

    def has_captcha(self):
        return Attr('//div[@class="g-recaptcha"]', 'data-sitekey', default=NotAvailable)(self.doc)

    def get_captcha_key(self):
        return Attr('//div[@class="g-recaptcha"]', 'data-sitekey')(self.doc)


class AjaxPage(JsonPage):
    def get_keylist(self):
        return (self.doc['data']['keys'], self.doc['data']['csrftoken'])

    def get_key_details(self):
        return (self.doc['data']['key']['apikey'], self.doc['data']['key']['secret'])

    def get_new_key_details(self):
        return (self.doc['data']['apikey'], self.doc['data']['secret'])

    def get_new_token(self):
        return self.doc['data']['csrftoken']


class APISettingsPage(HTMLPage):
    def get_token(self):
        dict = json.loads(Attr('//meta[@name="initjs-tag"]', 'content')(self.doc))
        return dict['u']['global']['csrftoken']


class BalancePage(JsonPage):
    def get_error(self):
        return self.doc['error']

    def iter_accounts(self):
        balance = self.doc['result']
        for item in balance:
            account = Account()
            account.id = item
            account.type = Account.TYPE_CHECKING
            # remove first symbol ('Z' or 'X'), but not for GNO or DASH
            account.currency = account.label = item[1:] if len(item) == 4 and item != "DASH" else item
            account.balance = Decimal(balance[item])

            yield account


class HistoryPage(JsonPage):
    def get_tradehistory(self, currency):
        transactions_list = []
        all_transactions = (x for x in self.doc['result']['ledger'].values() if currency in x['asset'])
        for item in all_transactions:
            transaction = Transaction()
            transaction.type = Transaction.TYPE_TRANSFER
            transaction.id = item['refid']
            transaction.amount = Decimal(item['amount'])
            transaction.date = date.fromtimestamp(item['time'])
            transaction.raw = item['type']
            transaction.commission = Decimal(item['fee'])
            transactions_list.append(transaction)

        return(sorted_transactions(transactions_list))
