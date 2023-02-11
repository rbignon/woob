# -*- coding: utf-8 -*-

# Copyright(C) 2017      Phyks (Lucas Verney)
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

from woob.browser.pages import HTMLPage, LoggedPage
from woob.browser.selenium import SeleniumPage, StablePageCondition
from woob.browser.filters.standard import CleanText, CleanDecimal, Date, Env, Format, Regexp
from woob.browser.filters.html import Attr, Link
from woob.browser.elements import ItemElement, ListElement, method
from woob.capabilities.base import NotAvailable
from woob.capabilities.bill import Subscription, Bill, Document, DocumentTypes


class LoginPage(SeleniumPage):
    def do_login(self, username, password):
        el = self.driver.find_element_by_xpath('//input[@id="userloginid"]')
        el.click()
        el.send_keys(username)

        el = self.driver.find_element_by_xpath('//button[@id="UsernameSubmitBtn"]')
        el.click()
        el = self.driver.find_element_by_xpath('//input[@id="userloginpass"]')
        self.browser.wait_until(StablePageCondition())
        el.send_keys(password)

        el = self.driver.find_element_by_xpath('//button[@data-analytics="connect-myfoncia-button"]')
        el.click()

    def get_error_msg(self):
        return CleanText('//div[@class="Dialog Dialog--warning Login-Step1"]')(self.doc)


class MyPropertyPage(LoggedPage, HTMLPage):
    @method
    class get_subscriptions(ListElement):
        item_xpath = '//li[contains(@class, "MyPropertiesSelector-item") and not(contains(@class, "MyPropertiesSelector-item--add"))]'

        class item(ItemElement):
            klass = Subscription

            obj_id = CleanText('./@data-property')
            obj_label = CleanText('.//strong')
            obj_subscriber = Regexp(CleanText('//a[@class="MainNav-item-logged"]'), r'Bonjour (.+)')


class DocumentsPage(LoggedPage, HTMLPage):
    @method
    class iter_documents(ListElement):
        item_xpath = '//article[contains(@class, "TeaserRow")]'

        class item(ItemElement):
            klass = Document

            obj_id = Format(
                '%s_%s',
                Env('subscription_id'),
                Attr('.', 'id')
            )
            obj_label = CleanText('.//p[@class="TeaserRow-desc"]')
            obj_date = Date(
                CleanText('.//p[@class="TeaserRow-date"]', default=NotAvailable),
                dayfirst=True,
                default=NotAvailable
            )
            obj_format = "pdf"
            obj_url = Link('.//a[@class="Download"]', default='')
            obj_type = DocumentTypes.REPORT

            def obj_has_file(self):
                return CleanText('.//a[@class="Download"]', default='')(self)


class FeesPage(LoggedPage, HTMLPage):
    @method
    class iter_fees(ListElement):
        item_xpath = '//article[contains(@class, "TeaserRow")]'

        class item(ItemElement):
            klass = Bill

            obj_id = Format(
                '%s_%s',
                Env('subscription_id'),
                Attr('.', 'id'),
            )
            obj_currency = 'EUR'
            obj_label = CleanText('.//p[@class="TeaserRow-desc"]')
            obj_total_price = CleanDecimal(CleanText('.//span[@class="nbPrice"]'), replace_dots=(' ', '€'))
            obj_date = Date(CleanText('.//p[@class="TeaserRow-date"]'), dayfirst=True)
            obj_duedate = obj_date
            obj_format = "pdf"
            obj_url = Link('.//a[@class="Download"]', default='')

            def obj_has_file(self):
                return CleanText('.//a[@class="Download"]', default='')(self)
