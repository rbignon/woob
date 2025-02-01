# -*- coding: utf-8 -*-

# Copyright(C) 2019      Antoine BOSSY
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


from woob.browser.elements import ItemElement, ListElement, SkipItem, method
from woob.browser.filters.html import Attr
from woob.browser.filters.standard import CleanDecimal, CleanText, Date, Field, Format
from woob.browser.pages import HTMLPage, LoggedPage
from woob.capabilities.bank import Account, Transaction
from woob.capabilities.base import NotAvailable


class LoginPage(HTMLPage):
    def login(self, login, password):
        form = self.get_form('//form[@id="frmMain"]')
        form["UserLogin"] = login
        form["UserPass"] = password
        form.submit()


class ProfilePage(HTMLPage):
    pass


class AccountsPage(LoggedPage, HTMLPage):
    @method
    class iter_accounts(ListElement):
        item_xpath = '//tr[has-class("ItemH23")]'

        class item(ItemElement):
            klass = Account

            # TODO: control all these attributes

            # obj_type = '??????'
            obj_id = CleanText("./td[position()=2]")
            obj_balance = CleanDecimal("./td[position()=6]", replace_dots=True)
            obj_label = Format("Millésime %s", Field("id"))
            obj_number = Field("id")
            obj_currency = "EUR"

            obj__page = Attr("./td//input", "name")

    def go_to_transactions_page(self, page):
        form = self.get_form('//form[@id="frmMain"]')
        form[f"{page}.x"] = 1
        form[f"{page}.y"] = 1
        form.submit()

    @method
    class iter_transactions(ListElement):
        item_xpath = '//tr[has-class("ItemH23")]'

        class item(ItemElement):
            klass = Transaction

            # TODO: control all these attributes

            def obj_date(self):
                maybe_date = CleanText("./td[position()=2]")(self)
                if maybe_date == "-":
                    raise SkipItem()

                return Date(CleanText("./td[position()=2]"), dayfirst=True)(self)

            obj_id = CleanText("./td[position()=3]")

            def obj_amount(self):
                amount = CleanDecimal("./td[position()=4]", replace_dots=True, default=NotAvailable)(self)

                if amount is NotAvailable:
                    return CleanDecimal("./td[position()=5]", replace_dots=True)(self)

                return amount * -1

            obj_currency = "EUR"

            def obj_label(self):
                label = CleanText("./td[position()=6]")(self)
                if label == "-":
                    return CleanText("./td[position()=7]")(self)

                return label

            obj_raw = Field("label")
