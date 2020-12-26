# -*- coding: utf-8 -*-

# flake8: compatible

# Copyright(C) 2012-2020  Budget Insight
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

from weboob.browser.filters.html import AbsoluteLink
from weboob.browser.pages import HTMLPage, LoggedPage, RawPage
from weboob.capabilities.profile import Profile
from weboob.tools.compat import parse_qsl, urlparse
from weboob.capabilities.bill import Subscription, Bill
from weboob.browser.elements import ListElement, ItemElement, method
from weboob.browser.filters.standard import CleanText, Field, Format, Date, CleanDecimal, Currency, Env, QueryValue


class LoginPage(HTMLPage):
    is_here = '//form[@class="form-login"]'

    def login(self, login, password):
        form = self.get_form('//form[@class="form-login"]')
        form['login-ident'] = login
        form['login-pwd'] = password
        form.submit()

    def get_error(self):
        return CleanText('//div[@class="flash flash-error"]')(self.doc)


class BillsPage(LoggedPage, HTMLPage):
    @method
    class iter_documents(ListElement):
        item_xpath = '//div[@class="table table-facture"]/div[@class="table__scrollable"]//div[@class="grid-l"]'

        class item(ItemElement):
            klass = Bill

            obj_id = Format('%s_%s', Env('sub'), Field('_raw_date'))
            obj_url = AbsoluteLink('.//div[has-class("download")]/a')
            obj_total_price = CleanDecimal.SI('.//div[has-class("amount")]')
            obj_currency = Currency('.//div[has-class("amount")]')
            obj_label = CleanText('.//div[has-class("date")]')
            obj_format = 'pdf'
            obj__raw_date = QueryValue(Field('url'), 'date')
            obj_date = Date(Field('_raw_date'))


class ProfilePage(LoggedPage, HTMLPage):
    @method
    class get_profile(ItemElement):
        klass = Profile

        obj_id = CleanText('//div[contains(text(), "Mon adresse email")]/..', children=False)
        obj_email = Field('id')
        obj_name = CleanText('//div[@class="current-user__infos"]/div[has-class("identite")]')
        obj_address = CleanText('//address')
        obj_phone = CleanText('//div[@class="current-user__infos"]/div[contains(text(), "Ligne")]/span', replace=[(' ', '')])


class PdfPage(RawPage):
    pass


class OfferPage(LoggedPage, HTMLPage):

    def fill_subscription(self, subscription):
        offer_name = CleanText('//div[@class="title"]')(self.doc)
        if offer_name:
            subscription.label = "%s - %s" % (subscription.id, offer_name)

    @method
    class get_first_subscription(ItemElement):
        klass = Subscription

        obj__userid = CleanText('.//div[contains(text(), "Identifiant")]/span')
        obj_id = CleanText('//div[@class="current-user__infos"]/div[3]/span', replace=[(' ', '')])
        obj_subscriber = CleanText('//div[@class="current-user__infos"]/div[has-class("identite")]')
        obj_label = Field('id')

    @method
    class iter_next_subscription(ListElement):
        item_xpath = '//div[@class="list-users"]/ul[@id="multi-ligne-selector"]/li/ul/li[@class="user"]/a'

        class item(ItemElement):
            klass = Subscription

            obj__userid = CleanText(QueryValue(AbsoluteLink('.'), 'switch-user'))
            obj_id = CleanText('./span[has-class("user-content")]/span[has-class("ico")]/following-sibling::text()', replace=[(' ', '')])
            obj_subscriber = CleanText('./span[has-class("user-content")]/span[has-class("name")]')
            obj_label = Field('id')
