# -*- coding: utf-8 -*-

# Copyright(C) 2017      P4ncake
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

from __future__ import unicode_literals


from weboob.browser.pages import HTMLPage, LoggedPage
from weboob.browser.elements import ItemElement, method, ListElement
from weboob.browser.filters.standard import (
    CleanText, CleanDecimal, Env,
    Regexp, Format, Date, Currency,
)
from weboob.browser.filters.html import Attr, AbsoluteLink
from weboob.capabilities.bill import Bill, Subscription


class LoginPage(HTMLPage):
    def login(self, login, password, captcha=None):
        form = self.get_form(xpath='//form[@action="/"]')

        form['email'] = login
        form['passwordV3'] = password
        if captcha is not None:
            form['g-recaptcha-response'] = captcha
        form.submit()

    def has_captcha(self):
        return self.doc.xpath('//div[@class="g-recaptcha"]')

    def get_captcha_key(self):
        return Attr('//div[@class="g-recaptcha"]', 'data-sitekey')(self.doc)

    def get_error_login(self):
        return CleanText('//div[@class="warning-text2"]')(self.doc)


class SubscriptionsPage(LoggedPage, HTMLPage):
    @method
    class get_item(ItemElement):
        klass = Subscription

        obj_subscriber = Format(
            '%s %s',
            CleanText('//label[@name="first_name"]'),
            CleanText('//label[@name="last_name"]')
        )
        obj_label = obj_id = Attr('//input[@id="booking_mail"]', 'value')


class DocumentsPage(LoggedPage, HTMLPage):
    @method
    class iter_documents(ListElement):
        item_xpath = '//div[@class="facture"]'

        class item(ItemElement):
            klass = Bill

            obj_id = Format('%s_%s', Env('subid'), Regexp(CleanText('.//div[@class="facture_ref"]'), r'(\d*$)'))
            obj_url = AbsoluteLink('.//div[@class="facture_pdf"]/a')
            obj_date = Date(CleanText('.//div[@class="facture_date"]'), dayfirst=True)
            obj_format = 'pdf'
            obj_label = CleanText('.//div[@class="facture_ref"]')
            obj_price = CleanDecimal.French('.//div[@class="facture_tarif"]/p')
            obj_currency = Currency('.//div[@class="facture_tarif"]/p')
