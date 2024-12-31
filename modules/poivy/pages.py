# -*- coding: utf-8 -*-

# Copyright(C) 2013-2014 Florent Fourcot
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

from woob.browser.elements import ItemElement, ListElement, method
from woob.browser.filters.html import Attr, Link
from woob.browser.filters.standard import CleanDecimal, CleanText, DateTime, Field, Format
from woob.browser.pages import HTMLPage, LoggedPage, pagination
from woob.capabilities.bill import Detail, Subscription
from woob.exceptions import ScrapingBlocked


class ErrorPage(HTMLPage):
    pass


class LoginPage(HTMLPage):

    def login(self, login, password):
        captcha = self.doc.xpath('//label[@class="label_captcha_input"]')
        if len(captcha) > 0:
            raise ScrapingBlocked('Too many connections from your IP address: captcha enabled')

        xpath_hidden = '//form[@id="newsletter_form"]/input[@type="hidden"]'
        hidden_id = Attr(xpath_hidden, "value")(self.doc)
        hidden_name = Attr(xpath_hidden, "name")(self.doc)

        form = self.get_form(xpath="//form[@class='form-detail']")
        form['login[username]'] = login
        form['login[password]'] = password
        form[hidden_name] = hidden_id
        form.submit()


class HomePage(LoggedPage, HTMLPage):

    @method
    class get_list(ListElement):
        item_xpath = '.'

        class item(ItemElement):
            klass = Subscription

            obj_id = CleanText('//span[@class="welcome-text"]/b')
            obj__balance = CleanDecimal(CleanText('//span[contains(@class, "balance")]'), replace_dots=False)
            obj_label = Format(u"Poivy - %s - %s €", Field('id'), Field('_balance'))


class HistoryPage(LoggedPage, HTMLPage):

    @pagination
    @method
    class get_calls(ListElement):
        item_xpath = '//table/tbody/tr'

        next_page = Link("//div[@class='date-navigator center']/span/a[contains(text(), 'Previous')]",
                         default=None)

        class item(ItemElement):
            klass = Detail

            obj_id = None
            obj_datetime = DateTime(CleanText('td[1] | td[2]'))
            obj_price = CleanDecimal('td[7]', replace_dots=False, default=0)
            obj_currency = u'EUR'
            obj_label = Format(u"%s from %s to %s - %s",
                               CleanText('td[3]'), CleanText('td[4]'),
                               CleanText('td[5]'), CleanText('td[6]'))


#TODO
class BillsPage(HTMLPage):
    pass
