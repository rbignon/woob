# -*- coding: utf-8 -*-

# Copyright(C) 2012-2019  Budget Insight

from __future__ import unicode_literals

from woob.browser.pages import LoggedPage, JsonPage
from woob.browser.elements import DictElement, ItemElement, method
from woob.browser.filters.standard import (
    Date, Format, CleanText,
    Currency, CleanDecimal, Env, Coalesce,
)
from woob.browser.filters.json import Dict
from woob.capabilities.bill import Subscription, Bill

from woob.capabilities import NotAvailable


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
