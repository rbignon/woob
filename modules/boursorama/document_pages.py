# -*- encoding: utf-8 -*-

# Copyright(C) 2020       Simon Bordeyne
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

from datetime import date

from weboob.browser.pages import HTMLPage, LoggedPage
from weboob.browser.elements import ListElement, ItemElement, method
from weboob.capabilities.bill import (
    Subscription, Document, DocumentTypes,
)
from weboob.browser.filters.standard import (
    CleanText, Field, Format,
    Regexp, Date, Env,
)
from weboob.browser.filters.html import Attr, Link
from weboob.tools.compat import urljoin


class BankStatementsPage(LoggedPage, HTMLPage):
    @property
    def account_keys(self):
        for el in self.doc.xpath('//select[@id="FiltersType_account"]//option'):
            # the first line is just here to tell the user to choose an account. Value is ""
            if el.values()[0]:
                yield el.values()[0]

    def submit_form(self, **data):
        defaults = {
            'filterIsin': '',
            'type': 'cc',
            'fromDate': '01/01/1970',  # epoch, so we fetch as much as possible
            'toDate': date.today().strftime("%d/%m/%Y"),
        }
        defaults.update(data)

        form = self.get_form(name="FiltersType")
        for key, value in defaults.items():
            form['FiltersType[%s]' % key] = value
        return form.submit().page

    @method
    class get_subscription(ItemElement):
        klass = Subscription

        def obj__statement_type(self):
            value = Attr('//select[@id="FiltersType_type"]//option[(@selected)]', 'value', default='cc')(self)
            if value == 'cc':
                return 'ccs'
            return value

        obj__account_key = Attr('//select[@id="FiltersType_account"]//option[(@selected)]', 'value')

        obj_id = Regexp(CleanText('//select[@id="FiltersType_account"]//option[(@selected)]'), r'(\d+)')
        obj_subscriber = CleanText('//span[contains(@class, "user__username pull-left")]')
        obj_label = obj_id

    # TODO: Handle pagination
    @method
    class iter_documents(ListElement):
        item_xpath = '//table/tbody/tr'

        class item(ItemElement):
            klass = Document

            obj_id = Format('%s_%s%s', Env('subid'), Field('date'), Env('statement_type'))
            obj_type = DocumentTypes.STATEMENT
            obj_url = CleanText('.//td[1]/a')
            obj_date = Date(CleanText('.//td[3]'))
            obj_format = CleanText('.//td[2]')
            obj_label = CleanText('.//td[1]/a')


class BankIdentityPage(LoggedPage, HTMLPage):
    @method
    class get_document(ListElement):
        item_xpath = '//table/tbody/tr'

        class item(ItemElement):
            klass = Document

            def condition(self):
                return Env('subid')(self) == Regexp(CleanText('.//td[1]/a'), r'(\d+)')(self)

            obj_id = Format('%s_RIB', Env('subid'))

            def obj_url(self):
                link = Link('.//td[1]/a')(self)
                return urljoin(self.page.url, urljoin(link, 'telecharger'))

            obj_date = Date(CleanText('.//td[3]'))
            obj_format = CleanText('.//td[2]')
            obj_label = CleanText('.//td[1]/a')
            obj_type = DocumentTypes.RIB
