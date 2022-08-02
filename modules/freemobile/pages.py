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

from woob.browser.filters.html import AbsoluteLink
from woob.browser.pages import HTMLPage, LoggedPage, RawPage
from woob.capabilities.profile import Profile
from woob.capabilities.bill import Subscription, Bill
from woob.browser.elements import ListElement, ItemElement, method
from woob.browser.filters.standard import CleanText, Field, Format, Date, CleanDecimal, Currency, Env, QueryValue


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
        obj_phone = CleanText(
            '//div[@class="current-user__infos"]/div[contains(text(), "Ligne")]/span',
            replace=[(" ", "")],
        )


class PdfPage(RawPage):
    pass


class OfferPage(LoggedPage, HTMLPage):

    def fill_subscription(self, subscription):
        offer_name = CleanText('//div[@class="title"]')(self.doc)
        if offer_name:
            subscription.label = "%s - %s" % (subscription._phone_number, offer_name)

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
