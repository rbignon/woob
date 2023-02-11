# -*- coding: utf-8 -*-

# Copyright(C) 2012-2021  Budget Insight
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

from dateutil.tz import gettz

from woob.browser.elements import DictElement, ItemElement, method
from woob.browser.pages import JsonPage
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import (
    CleanDecimal, CleanText, Coalesce, Currency, Env,
    FromTimestamp, Map,
)
from woob.capabilities.bank import Account, Transaction
from woob.capabilities.base import NotAvailable


class AccountPage(JsonPage):
    def get_account(self):
        account = Account()

        account.id = CleanText(Dict('id'))(self.doc)
        account.iban = CleanText(Dict('iban'))(self.doc)
        account.currency = Currency(Dict('currency'))(self.doc)
        account.type = Account.TYPE_CHECKING

        return account


class SpacesPage(JsonPage):
    @method
    class fill_account(ItemElement):
        obj_balance = CleanDecimal.SI(Dict('totalBalance'))

        def obj_label(self):
            for space in Dict('spaces')(self):
                if space['isPrimary']:
                    return CleanText().filter(space['name'])
            raise AssertionError('There should be a primary account.')


TRANSACTION_TYPES = {
    'PT': Transaction.TYPE_CARD,
    'AA': Transaction.TYPE_CARD,
    'CT': Transaction.TYPE_TRANSFER,
    'WEE': Transaction.TYPE_BANK,
    'DT': Transaction.TYPE_TRANSFER,
    'FT': Transaction.TYPE_TRANSFER,
    'DD': Transaction.TYPE_ORDER,
}


class TransactionsPage(JsonPage):
    @method
    class iter_history(DictElement):
        item_xpath = None

        class item(ItemElement):
            klass = Transaction

            obj_id = CleanText(Dict('id'))
            obj_amount = CleanDecimal.SI(Dict('amount'))
            obj_label = obj_raw = Coalesce(
                CleanText(Dict('merchantName', default=None), default=NotAvailable),
                CleanText(Dict('partnerName', default=None), default=NotAvailable),
                CleanText(Dict('referenceText', default=None), default=NotAvailable),
                default='',  # A transaction can have no label.
            )
            obj_date = FromTimestamp(Dict('createdTS'), tz=gettz('Europe/Paris'), millis=True)
            obj_rdate = FromTimestamp(Dict('visibleTS'), tz=gettz('Europe/Paris'), millis=True)
            obj_type = Map(Dict('type'), TRANSACTION_TYPES, default=Transaction.TYPE_UNKNOWN)
            obj_original_currency = Currency(Dict('originalCurrency', default=None), default=NotAvailable)
            obj_original_amount = CleanDecimal.SI(Dict('originalAmount', default=None), default=NotAvailable)

            obj__category_id = Dict('category')
            obj__is_coming = Dict('pending')

            def validate(self, obj):
                return Env('coming')(self) == obj._is_coming and obj.amount != 0


class TransactionsCategoryPage(JsonPage):
    def get_categories(self):
        categories_map = {}
        for category in self.doc:
            categories_map[category['id']] = category['name']
        return categories_map
