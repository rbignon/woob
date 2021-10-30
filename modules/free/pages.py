# -*- coding: utf-8 -*-

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

from __future__ import unicode_literals

from woob.browser.pages import HTMLPage, LoggedPage, RawPage
from woob.browser.filters.standard import CleanDecimal, CleanText, Env, Format, Field, Eval, Regexp, QueryValue, Slugify, Date
from woob.browser.elements import ListElement, ItemElement, method
from woob.browser.filters.html import Link
from woob.capabilities.bill import DocumentTypes, Bill, Subscription, Document
from woob.capabilities.profile import Profile
from woob.capabilities.base import NotAvailable
from woob.tools.date import parse_french_date


class LoginPage(HTMLPage):
    def login(self, login, password):
        form = self.get_form(id='log_form')
        form['login'] = login
        form['pass'] = password

        form.submit()

    def get_error(self):
        return CleanText('//div[has-class("loginalert")]')(self.doc)


class HomePage(LoggedPage, HTMLPage):
    @method
    class get_list(ListElement):
        class item(ItemElement):
            klass = Subscription

            obj_subscriber = Env('subscriber')
            obj_id = Env('subid')
            obj_label = obj_id

            def parse(self, el):
                username = self.page.browser.username
                try:
                    subscriber = CleanText('//div[@class="infos_abonne"]/ul/li[1]')(self)
                except UnicodeDecodeError:
                    subscriber = username
                self.env['subscriber'] = subscriber
                self.env['subid'] = username


class ConsolePage(LoggedPage, RawPage):
    pass


class SuiviPage(LoggedPage, RawPage):
    pass


class DocumentsPage(LoggedPage, HTMLPage):
    ENCODING = "latin1"

    def get_list(self):
        sub = Subscription()

        sub.subscriber = self.browser.username
        sub.id = sub.subscriber
        sub.label = sub.subscriber

        yield sub

    @method
    class get_documents(ListElement):
        item_xpath = "//ul[@class='pane']/li"

        class item(ItemElement):
            klass = Bill

            obj_id = Format('%s_%s', Env('subid'), QueryValue(Field("url"), "no_facture"))
            obj_url = Link("./span[1]/a", default=NotAvailable)
            obj_date = Env('date')
            obj_format = 'pdf'
            obj_label = Format("Facture %s", CleanText("./span[2]"))
            obj_total_price = CleanDecimal.French('./span[has-class("last")]')
            obj_currency = 'EUR'

            def parse(self, el):
                self.env['date'] = parse_french_date('01 %s' % CleanText('./span[2]')(self)).date()


class ProfilePage(LoggedPage, HTMLPage):
    def get_profile(self, subscriber):
        p = Profile()
        p.name = subscriber
        p.email = CleanText('//input[@name="email"]/@value')(self.doc) or NotAvailable
        p.phone = CleanText('//input[@name="portable"]/@value')(self.doc) or NotAvailable

        return p

    def set_address(self, profile):
        assert len(self.doc.xpath('//p/strong[contains(text(), " ")]')) == 1, 'There are several addresses.'
        profile.address = CleanText('//p/strong[contains(text(), " ")]')(self.doc) or NotAvailable


class ContractPage(LoggedPage, HTMLPage):
    @method
    class iter_documents(ListElement):
        item_xpath = (
            '//div[has-class("monabo")]//ul[has-class("no_arrow")]/li[not(@class)]//a'
        )

        class item(ItemElement):
            klass = Document
            obj_url = Link(".")
            obj_date = Date(
                CleanText(
                    'ancestor::div[contains(@class, "monabo")]//strong/span[@class="red"]'
                ),
                dayfirst=True,
            )
            obj_id = Format(
                "%s_%s_%s",
                Env("subscription_id"),
                Eval(lambda t: t.strftime("%Y%m%d"), Field("date")),
                Slugify(Regexp(Field("url"), r"([^/]+)\.pdf")),
            )
            obj_type = DocumentTypes.CONTRACT
            obj_label = Format(
                "%s (%s)",
                CleanText("ancestor::li"),
                Regexp(Field("url"), r"([^/]+)\.pdf"),
            )
            obj_format = "pdf"
