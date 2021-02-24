# -*- coding: utf-8 -*-

# Copyright(C) 2012-2019  Budget Insight

from __future__ import unicode_literals

from weboob.browser.pages import LoggedPage, JsonPage
from weboob.browser.elements import DictElement, ItemElement, method
from weboob.browser.filters.standard import (
    Date, Format, CleanText,
    Currency, CleanDecimal, Env,
)
from weboob.browser.filters.json import Dict
from weboob.capabilities.bill import Subscription, Bill


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

        class item(ItemElement):
            klass = Bill

            def condition(self):
                return 'Paid' in Dict('order/payment/paymentState')(self)

            obj_id = Format('%s_%s', Env('subid'), CleanText(Dict('order/id')))
            obj_number = CleanText(Dict('order/friendlyOrderId'))
            obj_date = Date(Dict('order/orderDate'))
            obj_currency = Currency(Dict('order/payment/paid/currency'))
            obj_total_price = CleanDecimal.SI(Dict('order/payment/paid/amount'))
            obj_url = Format(
                'https://www.thetrainline.com/fr/my-account/order/%s/expense-receipt',
                CleanText(Dict('order/id')),
            )
