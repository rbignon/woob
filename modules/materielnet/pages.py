# Copyright(C) 2016      Edouard Lambert
# Copyright(C) 2016-2022 Budget Insight
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

# flake8: compatible

import re

from woob.browser.elements import ItemElement, ListElement, method
from woob.browser.filters.html import Attr, Link
from woob.browser.filters.standard import Async, CleanDecimal, CleanText, Date, Field, Filter, Format, Regexp
from woob.browser.pages import HTMLPage, JsonPage, LoggedPage, PartialHTMLPage
from woob.capabilities.base import NotAvailable
from woob.capabilities.bill import Bill, Subscription
from woob.exceptions import BrowserIncorrectPassword


class LoginPage(PartialHTMLPage):
    def get_recaptcha_sitekey(self):
        return Attr('//div[@class="g-recaptcha"]', 'data-sitekey', default=NotAvailable)(self.doc)

    def login(self, login, password, captcha_response=None):
        maxlength = int(Attr('//input[@id="Email"]', 'data-val-maxlength-max')(self.doc))
        regex = Attr('//input[@id="Email"]', 'data-val-regex-pattern')(self.doc)
        # their regex is: ^([\w\-+\.]+)@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.)|(([\w-]+\.)+))([a-zA-Z]{2,15}|[0-9]{1,3})(\]?)$
        # but it is not very good, we escape - inside [] to avoid bad character range Exception
        regex = regex.replace(r'[\w-+\.]', r'[\w\-+\.]')

        if len(login) > maxlength:  # actually it's 60 char
            raise BrowserIncorrectPassword(Attr('//input[@id="Email"]', 'data-val-maxlength')(self.doc))

        if not re.match(regex, login):
            raise BrowserIncorrectPassword(Attr('//input[@id="Email"]', 'data-val-regex')(self.doc))

        form = self.get_form(xpath='//form[contains(@action, "/Login/Login")]')
        form['Email'] = login
        form['Password'] = password

        if captcha_response:
            form['g-recaptcha-response'] = captcha_response

        form.submit()

    def get_error(self):
        return CleanText('//span[contains(@class, "field-validation-error")]')(self.doc)


class CaptchaPage(HTMLPage):
    def get_error(self):
        return CleanText('//div[@class="captcha-block"]/p[1]/text()')(self.doc)


class ProfilePage(LoggedPage, HTMLPage):
    @method
    class get_subscriptions(ListElement):
        class item(ItemElement):
            klass = Subscription

            obj_subscriber = Format(
                '%s %s',
                Attr('//input[@id="FirstName"]', 'value'),
                Attr('//input[@id="LastName"]', 'value'),
            )
            obj_id = CleanText('//p[@class="NumCustomer"]/span')
            obj_label = Field('id')


class MyAsyncLoad(Filter):
    def __call__(self, item):
        link = self.select(self.selector, item)
        data = {'X-Requested-With': 'XMLHttpRequest'}
        if link:
            return item.page.browser.async_open(link, data=data)


class DocumentsPage(LoggedPage, PartialHTMLPage):
    @method
    class get_documents(ListElement):
        item_xpath = '//div[@class="historic-table"]'

        class item(ItemElement):
            klass = Bill

            def condition(self):
                return 'track-error' not in Attr('./div[contains(@class, "track")]', 'class', default='')(self)

            load_details = Link('.//div[has-class("historic-cell--details")]/a') & MyAsyncLoad

            obj_id = Regexp(CleanText('./div[contains(@class, "ref")]'), r'N. (.*)')
            obj_label = Format('Commande N°%s', Field('id'))
            obj_url = Async('details') & Link('//a[contains(@class, "o-btn--pdf")]', default=NotAvailable)
            obj_date = Date(CleanText('./div[contains(@class, "date")]'), dayfirst=True)
            obj_format = 'pdf'
            # cents in price will be be separated with € like : 1 234€56
            obj_total_price = CleanDecimal('./div[contains(@class, "price")]', replace_dots=(' ', '€'))
            obj_currency = 'EUR'


class DocumentsDetailsPage(LoggedPage, PartialHTMLPage):
    pass


class PeriodPage(LoggedPage, JsonPage):
    def get_periods(self):
        return self.doc
