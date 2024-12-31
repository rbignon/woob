# -*- coding: utf-8 -*-

# Copyright(C) 2022 Budget Insight
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

from woob.browser.elements import DictElement, ItemElement, method
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import CleanDecimal, CleanText, Coalesce, Currency, Date, Env, Format
from woob.browser.pages import JsonPage, LoggedPage
from woob.capabilities import NotAvailable
from woob.capabilities.bill import Bill, Subscription

from .akamai import AkamaiHTMLPage


class HomePage(AkamaiHTMLPage):
    def get_akamai_url(self):
        url = super(HomePage, self).get_akamai_url()
        if url.endswith('.js'):
            # wrong url, the good one is very probably missing
            return
        return url


class SigninPage(JsonPage):
    @property
    def logged(self):
        return Dict('authenticated', default=False)(self.doc) is True

    def get_error(self):
        return Dict('message', default=None)(self.doc)


class UserPage(LoggedPage, JsonPage):
    @method
    class get_subscription(ItemElement):
        klass = Subscription

        obj_id = CleanText(Dict('id'))
        obj_subscriber = Format(
            '%s %s',
            CleanText(Dict('firstName')),
            CleanText(Dict('surname')),
        )
        obj_label = CleanText(Dict('email'))


class DocumentsPage(LoggedPage, JsonPage):
    @method
    class iter_documents(DictElement):
        item_xpath = 'pastBookings/results'
        # when the seller is ouigo we have duplicate data
        ignore_duplicate = True

        class item(ItemElement):
            klass = Bill

            def condition(self):
                return 'COMPLETE' in Dict('order/state')(self)

            obj_id = Format('%s_%s', Env('subid'), CleanText(Dict('order/id')))
            obj_label = Format(
                '%s to %s',
                CleanText(Dict('booking/origin')),
                CleanText(Dict('booking/destination')),
            )
            obj_number = CleanText(Dict('order/friendlyOrderId'))
            obj_date = Date(Dict('order/orderDate'))
            obj_currency = Coalesce(
                Currency(Dict('order/payment/paid/currency', default=''), default=NotAvailable),
                Currency(Dict('order/invoices/0/currencyCode', default=''), default=NotAvailable)
            )
            obj_total_price = Coalesce(
                CleanDecimal.SI(Dict('order/payment/paid/amount', default=''), default=NotAvailable),
                CleanDecimal.SI(Dict('order/invoices/0/totalAmount', default=''), default=NotAvailable)
            )
            obj_url = Format(
                'https://www.thetrainline.com/fr/my-account/order/%s/expense-receipt',
                CleanText(Dict('order/id')),
            )
