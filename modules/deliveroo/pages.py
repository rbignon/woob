# -*- coding: utf-8 -*-

# Copyright(C) 2012-2022  Budget Insight
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


import json

from weboob.browser.pages import HTMLPage, JsonPage, LoggedPage, pagination
from weboob.browser.elements import ItemElement, ListElement, method
from weboob.browser.filters.standard import CleanText, CleanDecimal, Env, Regexp, Format, Async, AsyncLoad
from weboob.browser.filters.html import Link
from weboob.capabilities.bill import Bill, Subscription
from weboob.capabilities.base import NotAvailable
from weboob.tools.date import parse_french_date


def MyDecimal(*args, **kwargs):
    kwargs.update(replace_dots=True, default=NotAvailable)
    return CleanDecimal(*args, **kwargs)


class LoginPage(JsonPage):
    pass


class ProfilPage(LoggedPage, HTMLPage):
    @method
    class get_item(ItemElement):
        klass = Subscription

        obj_subscriber = CleanText(Env('subscriber'))
        obj_id = CleanText(Env('id'))

        def obj_label(self):
            return self.page.browser.username

        def parse(self, el):
            data = Regexp(CleanText('//script[contains(., "ROO_PAGE_DATA")]'), r'var ROO_PAGE_DATA = (.*?);')(self)
            user = json.loads(data).get('user')

            self.env['id'] = str(user.get('id'))
            self.env['subscriber'] = user.get('full_name')


class DocumentsPage(LoggedPage, HTMLPage):
    @pagination
    @method
    class get_documents(ListElement):
        item_xpath = '//ul[has-class("user--history-list")]/li/a'

        next_page = Link('//a[@class="pagination-link next"]', default=None)

        class item(ItemElement):
            klass = Bill

            load_details = Link('.') & AsyncLoad

            obj_id = Format('%s_%d', Env('subid'), CleanDecimal(Env('id')))
            obj_format = u"pdf"
            obj_label = Format(u'Facture %d', CleanDecimal(Env('id')))
            obj_type = u"bill"
            obj_price = MyDecimal(Env('price'))

            def obj__url(self):
                return Async('details', Link(u'.//a[contains(., "Reçu")]', default=NotAvailable))(self)

            def obj_date(self):
                return parse_french_date(CleanText(u'.//span[@class="history-col-date"]')(self)[:-6]).date()

            def obj_currency(self):
                return Bill.get_currency(CleanText(Env('price'))(self))

            def parse(self, el):
                self.env['id'] = Regexp(Link(u'.'), r'/orders/(.*)')(self)
                self.env['price'] = CleanText(u'.//span[@class="history-amount"]')(self)

            def condition(self):
                return CleanText('.//span[has-class("history-col-status") and not(has-class("status-failed"))]')(self)
