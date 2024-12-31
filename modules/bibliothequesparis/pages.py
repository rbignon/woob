# -*- coding: utf-8 -*-

# Copyright(C) 2017      Vincent A
#
# This file is part of a woob module.
#
# This woob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This woob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this woob module. If not, see <http://www.gnu.org/licenses/>.

from datetime import datetime

from woob.browser.elements import DictElement, ItemElement, method
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import Regexp
from woob.browser.pages import JsonPage, LoggedPage
from woob.capabilities.base import UserError
from woob.capabilities.library import Book


class LoginPage(JsonPage):
    @property
    def logged(self):
        return self.doc['success']


class JsonMixin(JsonPage):
    def on_load(self):
        if not self.doc['success']:
            for err in self.doc.get('errors', []):
                raise Exception(err['msg'])

        # at this point, success is true, but that doesn't really mean anything
        if isinstance(self.doc['d'], list) and self.doc['d']:
            # does this still happen?
            msg = self.doc['d'][0].get('ErrorMessage')
            if msg:
                raise UserError(msg)
        elif isinstance(self.doc['d'], dict) and self.doc['d'].get('Errors'):
            msg = self.doc['d']['Errors'][0].get('Value')
            if msg:
                raise UserError(msg)


class LoansPage(LoggedPage, JsonPage):
    @method
    class get_loans(DictElement):
        item_xpath = 'd/Loans'

        class item(ItemElement):
            klass = Book

            obj_url = Dict('TitleLink')
            obj_id = Dict('Id')
            obj_name = Dict('Title')

            def obj_date(self):
                # 1569967200000+0200 is 2019-10-02 00:00:00 +0200
                # but it's considered by the library to be 2019-10-01!
                return datetime.fromtimestamp(int(Regexp(Dict('WhenBack'), r'\((\d+)000')(self)) - 3600).date()

            obj_location = Dict('Location')

            def obj__renew_data(self):
                return self.el


class RenewPage(LoggedPage, JsonMixin):
    pass


class SearchPage(LoggedPage, JsonPage):
    @method
    class iter_books(DictElement):
        item_xpath = 'd/Results'

        class item(ItemElement):
            klass = Book

            obj_url = Dict('FriendlyUrl')
            obj_id = Dict('Resource/RscId')
            obj_name = Dict('Resource/Ttl')
            obj_author = Dict('Resource/Crtr', default=None)

    def get_max_page(self):
        return self.doc['d']['SearchInfo']['PageMax']
