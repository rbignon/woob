# -*- coding: utf-8 -*-

# Copyright(C) 2015      Vincent Paredes
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

from woob.capabilities.bill import Bill, Subscription
from woob.browser.pages import HTMLPage, LoggedPage, JsonPage
from woob.browser.filters.standard import CleanDecimal, CleanText, Env, Format, DateTime
from woob.browser.filters.html import Attr
from woob.browser.filters.json import Dict
from woob.browser.elements import ListElement, ItemElement, method, DictElement
from woob.exceptions import ActionNeeded, AuthMethodNotImplemented


class LoginPage(HTMLPage):
    def on_load(self):
        if self.doc.xpath('//p[contains(text(), "You have activated the double factor authentication")]'):
            raise AuthMethodNotImplemented('Two-Factor authentication is not supported.')

    def is_logged(self):
        return not self.doc.xpath('//input[@name="credentialToken"]')

    def login(self, login, password):
        form = self.get_form('//form[@class="pagination-centered"]')
        # because name attribute for login and password change each time we call this page
        user = Attr('//form[@class="pagination-centered"]//input[@type="text"]', 'name')(self.doc)
        pwd = Attr('//form[@class="pagination-centered"]//input[@type="password"]', 'name')(self.doc)

        form[user] = login
        form[pwd] = password
        form.submit()

    def get_error_message(self):
        return CleanText('//form[@class="pagination-centered"]/div[@class="error"]')(self.doc)

    # There is 2 double auth method
    # One activated by the user, that we don't handle,
    # The other, spawning sometimes at first login, that we can handle.

    def check_user_double_auth(self):
        double_auth = self.doc.xpath('//input[@id="codeSMS"]')

        if double_auth:
            raise ActionNeeded(CleanText('(//div[contains(., "Two-Factor")])[5]')(self.doc))

    def check_website_double_auth(self):
        double_auth = self.doc.xpath('//input[@id="emailCode"]')

        return bool(double_auth)

    def get_otp_message(self):
        return CleanText('//div[@class="control-group" and contains(., "email")]')(self.doc)

    def get_security_form(self):
        return self.get_form()


class ProfilePage(LoggedPage, JsonPage):
    @method
    class get_subscriptions(ListElement):
        class item(ItemElement):
            klass = Subscription

            obj_label = CleanText(Dict('nichandle'))
            obj_subscriber = Format("%s %s", CleanText(Dict('firstname')), CleanText(Dict('name')))
            obj_id = CleanText(Dict('nichandle'))


class BillItem(ItemElement):
    klass = Bill

    obj_id = Format('%s.%s', Env('subid'), Dict('orderId'))
    obj_total_price = CleanDecimal.SI(Dict('priceWithTax/value'))
    obj_format = 'pdf'
    obj_url = Dict('pdfUrl')
    obj_label = Format('Facture %s', Dict('orderId'))


class BillsPage(LoggedPage, JsonPage):
    @method
    class get_documents(DictElement):
        item_xpath = 'list/results'

        class item(BillItem):
            obj_date = DateTime(Dict('billingDate'))


class RefundsPage(LoggedPage, JsonPage):
    @method
    class get_documents(DictElement):
        item_xpath = 'list/results'

        class item(BillItem):
            obj_date = DateTime(Dict('date'))
            obj_total_price = CleanDecimal.SI(Dict('priceWithTax/value'), sign='-')
