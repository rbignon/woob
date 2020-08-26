# -*- coding: utf-8 -*-

# Copyright(C) 2020      Vincent A
#
# This file is part of a weboob module.
#
# This weboob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This weboob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this weboob module. If not, see <http://www.gnu.org/licenses/>.

# flake8: compatible

from __future__ import unicode_literals

from weboob.browser.elements import (
    ItemElement, ListElement, method,
)
from weboob.browser.pages import HTMLPage
from weboob.browser.filters.standard import (
    Date, CleanDecimal, CleanText, Format, Regexp, QueryValue,
)
from weboob.browser.filters.html import (
    AbsoluteLink, Attr, FormValue,
)
from weboob.capabilities.base import NotAvailable
from weboob.capabilities.address import PostalAddress
from weboob.capabilities.profile import Person
from weboob.capabilities.bill import (
    Subscription, Bill,
)


class LoggedMixin:
    @property
    def logged(self):
        return bool(self.doc.xpath('//a[@id="logout"]'))


class BillsPage(LoggedMixin, HTMLPage):
    @method
    class iter_other_subscriptions(ListElement):
        item_xpath = '//li[@id="contract-switch"]//a[@role="menuitem"][@href]'

        class item(ItemElement):
            klass = Subscription

            obj_url = AbsoluteLink('.')
            obj_id = QueryValue(obj_url, 'c')
            obj_number = Regexp(CleanText('.'), r'(CNT-\d+-\d+)')
            obj_label = Format(
                '%s %s',
                CleanText('./span', children=False),
                obj_number,
            )

    @method
    class iter_documents(ListElement):
        item_xpath = '//div[@id="invoices-container"]/ul/li'

        class item(ItemElement):
            klass = Bill

            obj_id = Attr('.', 'data-invoice-id')

            obj_total_price = CleanDecimal.French('.//div[has-class("amount")]')
            obj_currency = 'EUR'

            obj_date = Date(CleanText('.//div[has-class("dueDate")]'), dayfirst=True)

            obj_format = 'pdf'

            def obj_url(self):
                url = AbsoluteLink('.//a[@target="_blank"]')(self)
                if '//download' in url:
                    return NotAvailable
                return url

            def obj_has_file(self):
                return bool(self.obj_url())


class ProfilePage(LoggedMixin, HTMLPage):
    @method
    class get_profile(ItemElement):
        klass = Person

        obj_name = FormValue('//input[@name="name"]')
        obj_email = FormValue('//input[@name="email"]')
        obj_phone = Format(
            '%s%s',
            Regexp(
                CleanText(FormValue('//select[@id="phone_number_indic"]')),
                r'\+\d+'
            ),
            FormValue('//input[@id="phone_number"]')
        )
        obj_country = 'France'

        class obj_postal_address(ItemElement):
            klass = PostalAddress

            # there can be a lot of whitespace in city name
            obj_city = CleanText(FormValue('//select[@id="cities"]'))

            obj_street = Format(
                '%s %s',
                FormValue('//input[@name="num"]'),
                FormValue('//input[@name="street"]')
            )
            obj_postal_code = FormValue('//input[@name="zip_code"]')
            obj_country = 'France'

    def fill_sub(self, sub):
        sub._profile = self.get_profile()
        sub.subscriber = sub._profile.name
