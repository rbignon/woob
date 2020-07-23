# -*- coding: utf-8 -*-

# Copyright(C) 2020  budget-insight
#
# This file is part of weboob.
#
# weboob is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# weboob is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with weboob. If not, see <http://www.gnu.org/licenses/>.

# flake8: compatible

from __future__ import unicode_literals

import datetime

from weboob.browser.pages import LoggedPage, JsonPage
from weboob.browser.elements import method, DictElement, ItemElement
from weboob.browser.filters.json import Dict
from weboob.browser.filters.standard import (
    Format, BrowserURL, Env,
)
from weboob.capabilities.bill import Document, DocumentTypes


class StatementsPage(LoggedPage, JsonPage):
    @method
    class iter_documents(DictElement):
        item_xpath = '*/statementsMetadata'

        class item(ItemElement):
            klass = Document

            obj_type = DocumentTypes.STATEMENT
            obj_format = 'pdf'

            obj_id = Format('%s.%s', Env('subscription'), Dict('id'))

            def obj_date(self):
                # does the "day" key actually exist?
                return datetime.date(self.el['year'], self.el['month'], self.el.get('day', 1))

            obj_label = Format('%s', obj_date)

            obj_url = BrowserURL(
                'statement_dl',
                account_uid=Env('subscription'),
                year=Dict('year'),
                month=Dict('month')
            )
