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

from __future__ import unicode_literals

import json

from weboob.browser.filters.json import Dict
from weboob.browser.pages import HTMLPage, LoggedPage, pagination, JsonPage
from weboob.browser.elements import ItemElement, method, DictElement
from weboob.browser.filters.standard import CleanText, CleanDecimal, Env, Regexp, Format, Currency
from weboob.browser.filters.html import Attr
from weboob.capabilities.bill import Bill, Subscription
from weboob.capabilities.base import NotAvailable
from weboob.tools.date import parse_french_date
from weboob.tools.compat import urlparse, parse_qsl


def MyDecimal(*args, **kwargs):
    kwargs.update(replace_dots=True, default=NotAvailable)
    return CleanDecimal(*args, **kwargs)


class HomePage(HTMLPage):
    pass


class LoginPage(HTMLPage):
    def get_csrf_token(self):
        return Attr('//meta[@name="csrf-token"]', 'content')(self.doc)


class ProfilePage(LoggedPage, HTMLPage):
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


class DocumentsPage(LoggedPage, JsonPage):
    @pagination
    @method
    class get_documents(DictElement):
        item_xpath = 'orders'

        def next_page(self):
            if not self.objects:
                return

            browser = self.page.browser
            assert 'consumer_auth_token' in browser.session.cookies
            headers = {'authorization': 'Bearer %s' % browser.session.cookies['consumer_auth_token']}
            params = dict(parse_qsl(urlparse(browser.url).query))
            params['offset'] = int(params['offset']) + 25

            return browser.documents.go(subid=Env('subid')(self), params=params, headers=headers)

        class item(ItemElement):
            klass = Bill

            obj_id = Format('%s_%d', Env('subid'), CleanDecimal(Dict('id')))
            obj_format = 'pdf'
            obj_label = Format('Facture %d', CleanDecimal(Dict('id')))
            obj_price = CleanDecimal.SI(Dict('total'))
            obj_currency = Currency(CleanText(Dict('currency_code')))
            obj_url = Format('%s/fr/order/receipt/%s', Env('baseurl'), CleanDecimal(Dict('id')))

            def obj_date(self):
                return parse_french_date(CleanText(Dict('delivered_at'))(self))

            def condition(self):
                return CleanText(Dict('status'))(self).lower() not in ('failed', 'rejected', 'canceled')
