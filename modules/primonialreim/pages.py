# Copyright(C) 2019      Vincent A
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

import datetime
import json
import re
from decimal import Decimal

from woob.browser.elements import ItemElement, ListElement, method
from woob.browser.filters.html import AbsoluteLink
from woob.browser.filters.standard import CleanText, Format, Regexp
from woob.browser.pages import HTMLPage, LoggedPage
from woob.capabilities.bank.base import Account
from woob.capabilities.bill import Document, DocumentTypes


class LoginPage(HTMLPage):
    def do_login(self, username, password):
        form = self.get_form(xpath="//form[contains(@action, 'login')]")

        url = form.el.attrib["action"]
        token = re.search(r"INSTANCE_([a-zA-Z0-9]+)_", url)[1]

        form[f"_com_preim_portlet_login_PreimLoginPortlet_INSTANCE_{token}_username"] = username
        form[f"_com_preim_portlet_login_PreimLoginPortlet_INSTANCE_{token}_password"] = password
        form.submit()


class AfterLoginPage(LoggedPage, HTMLPage):
    pass


class AccountsPage(LoggedPage, HTMLPage):
    def iter_accounts(self):
        jdata = json.loads(self.doc.xpath("//div/@js-new-graph[contains(., 'bar')]")[0])
        jdata = {item["legendText"]: item["dataPoints"] for item in jdata["data"]}
        for jpoint in jdata["Valeur totale d achat"]:
            yield Account.from_dict(
                dict(
                    id=jpoint["label"].lower().replace(" ", ""),
                    label=jpoint["label"],
                    balance=Decimal(str(jpoint["y"])),
                    type=Account.TYPE_REAL_ESTATE,
                )
            )


class TaxDocsPage(LoggedPage, HTMLPage):
    @method
    class iter_documents(ListElement):
        item_xpath = "//a[contains(@href, '.pdf')]"

        class item(ItemElement):
            klass = Document

            obj_type = DocumentTypes.NOTICE
            obj_format = "pdf"

            obj_url = AbsoluteLink(".")
            obj_id = Regexp(obj_url, r"/([^/]+)\.pdf")

            obj__year = Regexp(obj_url, r"(\d+)\.pdf")
            obj_label = Format("%s %s", CleanText("."), obj__year)

            def obj_date(self):
                return datetime.date(int(self.obj._year) + 1, 1, 1)
