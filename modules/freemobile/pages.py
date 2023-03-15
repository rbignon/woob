# -*- coding: utf-8 -*-

# flake8: compatible

# Copyright(C) 2012-2020  Budget Insight
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

import re

from dateutil.relativedelta import relativedelta

from woob.browser.filters.html import AbsoluteLink, Link
from woob.browser.pages import HTMLPage, LoggedPage, RawPage
from woob.capabilities.address import PostalAddress
from woob.capabilities.base import NotAvailable
from woob.capabilities.profile import Profile
from woob.capabilities.bill import Subscription, Bill
from woob.browser.elements import ListElement, ItemElement, method, SkipItem
from woob.browser.filters.standard import (
    CleanText, Field, Format, Date, CleanDecimal, Currency, Env, Filter,
    QueryValue,
)
from woob.tools.date import parse_french_date


class FormatDate(Filter):
    def __init__(self, pattern, selector):
        super(FormatDate, self).__init__(selector)
        self.pattern = pattern

    def filter(self, _date):
        return _date.strftime(self.pattern)


class LoginPage(HTMLPage):
    @property
    def logged(self):
        return self.doc.xpath('//div[@class="list-users"]')

    def login(self, login, password):
        form = self.get_form('//form[@class="form-login"]')
        form['login-ident'] = login
        form['login-pwd'] = password
        form.submit()

    def get_error(self):
        return CleanText('//div[has-class("flash")]')(self.doc)


class BillsPage(LoggedPage, HTMLPage):
    @method
    class iter_documents(ListElement):
        item_xpath = '//div[@class="table table-facture"]//div[@class="grid-l"]'

        def store(self, obj):
            # This code enables doc_id when there
            # are several docs with the exact same id
            # sometimes we have two docs on the same date
            _id = obj.id
            n = 1
            while _id in self.objects:
                n += 1
                _id = '%s-%s' % (obj.id, n)
            obj.id = _id
            self.objects[obj.id] = obj
            return obj

        class item(ItemElement):
            klass = Bill

            obj_url = AbsoluteLink('.//div[has-class("download")]/a')
            obj_total_price = CleanDecimal.SI('.//div[has-class("amount")]')
            obj_currency = Currency('.//div[has-class("amount")]')
            obj_format = 'pdf'
            obj__raw_date = QueryValue(Field('url'), 'date')

            def obj__date_recap(self):
                # Unfortunately the date of those 'recap' documents is lost (not
                # present in url, etc...) and is only available in the PDFs
                # themselves.
                # Arbitrarily, we set it to the last day of month.
                dt = Date(
                    Format("1 %s", CleanText('.//div[has-class("date")]')),
                    parse_func=parse_french_date,
                    dayfirst=True,
                )(self)
                dt += relativedelta(months=1, days=-1)
                return dt

            def obj_id(self):
                if ("pdfrecap" in Field("url")(self)) != Env("is_recapitulatif")(self):
                    raise SkipItem()
                if Env("is_recapitulatif")(self):
                    return Format(
                        "%s_%s", Env("sub"), FormatDate("%Y%m", Field("_date_recap"))
                    )(self)
                return Format("%s_%s", Env("sub"), Field("_raw_date"))(self)

            def obj_label(self):
                if Env("is_recapitulatif")(self):
                    return Format(
                        "Multiligne - %s", CleanText('.//div[has-class("date")]')
                    )(self)
                return Format(
                    "%s - %s",
                    CleanText(
                        '//div[@class="table-container"]/p[@class="table-sub-title"]'
                    ),
                    CleanText('.//div[has-class("date")]'),
                )(self)

            def obj_date(self):
                if Env("is_recapitulatif")(self):
                    return Field("_date_recap")(self)
                return Date(Field("_raw_date"))(self)


class ProfilePage(LoggedPage, HTMLPage):
    @method
    class get_profile(ItemElement):
        klass = Profile

        obj_id = CleanText('//div[contains(text(), "Mon adresse email")]/..', children=False)
        obj_email = Field('id')
        obj_name = CleanText('//div[contains(text(), "Titulaire")]/..', children=False)
        obj_phone = CleanText(
            '//div[@class="current-user__infos"]/div[contains(text(), "Ligne")]/span',
            replace=[(" ", "")],
        )

        class obj_postal_address(ItemElement):
            klass = PostalAddress

            obj_full_address = Env('full_address', default=NotAvailable)
            obj_street = Env('street', default=NotAvailable)
            obj_postal_code = Env('postal_code', default=NotAvailable)
            obj_city = Env('city', default=NotAvailable)

            def parse(self, obj):
                full_address = CleanText('//address')(self)
                self.env['full_address'] = full_address
                m = re.search(r'(\d{1,4}.*) (\d{5}) (.*)', full_address)
                if m:
                    street, postal_code, city = m.groups()
                    self.env['street'] = street
                    self.env['postal_code'] = postal_code
                    self.env['city'] = city


class PdfPage(RawPage):
    pass


class OfferPage(LoggedPage, HTMLPage):

    def fill_subscription(self, subscription):
        subscription._is_recapitulatif = False
        subscription._real_id = subscription.id
        offer_name = CleanText('//div[@class="title"]')(self.doc)
        if offer_name:
            subscription.label = "%s - %s" % (subscription._phone_number, offer_name)

    def get_first_subscription_id(self):
        """Return the first subscription id if available."""
        return QueryValue(
            Link(
                '//div[@class="list-users"]/ul[@id="multi-ligne-selector"]'
                + '/li/ul/li[1]/a',
                default=None,
            ),
            'switch-user',
            default=None,
        )(self.doc)

    @method
    class get_first_subscription(ItemElement):
        klass = Subscription

        obj_id = CleanText('.//div[contains(text(), "Identifiant")]/span')
        obj__phone_number = CleanText('//div[@class="current-user__infos"]/div[3]/span', replace=[(' ', '')])
        obj_subscriber = CleanText('//div[@class="current-user__infos"]/div[has-class("identite")]')
        obj_label = Field('id')

    @method
    class iter_next_subscription(ListElement):
        item_xpath = '//div[@class="list-users"]/ul[@id="multi-ligne-selector"]/li/ul/li[@class="user"]/a'

        class item(ItemElement):
            klass = Subscription

            obj_id = CleanText(QueryValue(AbsoluteLink('.'), 'switch-user'))
            obj__phone_number = CleanText(
                './span[has-class("user-content")]/span[has-class("ico")]/following-sibling::text()',
                replace=[(" ", "")],
            )
            obj_subscriber = CleanText('./span[has-class("user-content")]/span[has-class("name")]')
            obj_label = Field('id')


class OptionsPage(LoggedPage, HTMLPage):
    def get_api_key(self):
        api_key = self.doc.xpath('//div[has-class("page")]//div[@id="opt_secret-key"]')
        if api_key:
            return api_key[0].text.strip()
        else:
            return None
