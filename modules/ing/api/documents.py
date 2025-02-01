# Copyright(C) 2020 Powens
#
# This file is part of woob.
#
# woob is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# woob is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with woob. If not, see <http://www.gnu.org/licenses/>.

# flake8: compatible

import datetime

from woob.browser.elements import DictElement, ItemElement, method
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import BrowserURL, Env, Format
from woob.browser.pages import JsonPage, LoggedPage
from woob.capabilities.bill import Document, DocumentTypes


class StatementsPage(LoggedPage, JsonPage):
    @method
    class iter_documents(DictElement):
        item_xpath = "*/statementsMetadata"

        class item(ItemElement):
            klass = Document

            obj_type = DocumentTypes.STATEMENT
            obj_format = "pdf"

            obj_id = Format("%s.%s", Env("subscription"), Dict("id"))

            def obj_date(self):
                # does the "day" key actually exist?
                return datetime.date(self.el["year"], self.el["month"], self.el.get("day", 1))

            obj_label = Format("%s", obj_date)

            obj_url = BrowserURL(
                "statement_dl", account_uid=Env("subscription"), year=Dict("year"), month=Dict("month")
            )
