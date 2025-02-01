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

import time

from woob.browser.elements import DictElement, ItemElement, ListElement, method
from woob.browser.filters.html import Attr
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import CleanDecimal, CleanText, DateTime, Env, Format
from woob.browser.pages import HTMLPage, JsonPage, LoggedPage
from woob.capabilities.bill import Bill, Subscription


class LoginPage(HTMLPage):
    def is_logged(self):
        return self.doc.xpath('//div[@class="already-logged-content"]')

    def login(self, login, password):
        form = self.get_form('//form[@id="login-form"]')
        # because name attribute for login and password change each time we call this page
        user = Attr('//form[@id="login-form"]//input[@id="account"]', "name")(self.doc)
        pwd = Attr('//form[@id="login-form"]//input[@id="password"]', "name")(self.doc)

        form[user] = login
        form[pwd] = password
        form.submit()

    def get_error_message(self):
        return CleanText('//form[@id="login-form"]/div[@class="error"]')(self.doc)

    # There is 2 double auth method
    # One activated by the user, that we can handle,
    # The other, spawning sometimes at first login, that we can also handle.

    def check_user_double_auth(self):
        double_auth = self.doc.xpath('//p[contains(text(), "You have activated the double factor authentication")]')
        double_auth2 = self.doc.xpath('//div[@class="mfa-title" and contains(text(), "Two-Factor authentication")]')
        return bool(double_auth) or bool(double_auth2)

    def maybe_switch_user_double_auth(self, method):
        form = self.get_form('//form[@id="form-2fa" or @id="2fa"]')
        if form["change2FA"] != method:
            form["change2FA"] = method
            time.sleep(0.5)
            form.submit()

    def submit_user_double_auth(self, method, value):
        form = self.get_form('//form[@id="form-2fa" or @id="2fa"]')
        form[method] = value
        form["otpMethod"] = method
        time.sleep(0.5)
        form.submit()

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

            obj_label = CleanText(Dict("nichandle"))
            obj_subscriber = Format("%s %s", CleanText(Dict("firstname")), CleanText(Dict("name")))
            obj_id = CleanText(Dict("nichandle"))


class BillItem(ItemElement):
    klass = Bill

    obj_id = Format("%s.%s", Env("subid"), Dict("orderId"))
    obj_total_price = CleanDecimal.SI(Dict("priceWithTax/value"))
    obj_format = "pdf"
    obj_url = Dict("pdfUrl")
    obj_label = Format("Facture %s", Dict("orderId"))


class BillsPage(LoggedPage, JsonPage):
    @method
    class get_documents(DictElement):
        item_xpath = "list/results"

        class item(BillItem):
            obj_date = DateTime(Dict("billingDate"))


class RefundsPage(LoggedPage, JsonPage):
    @method
    class get_documents(DictElement):
        item_xpath = "list/results"

        class item(BillItem):
            obj_date = DateTime(Dict("date"))
            obj_total_price = CleanDecimal.SI(Dict("priceWithTax/value"), sign="-")
