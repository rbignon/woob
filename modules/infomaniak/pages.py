# -*- coding: utf-8 -*-

# Copyright(C) 2017      Vincent A

# flake8: compatible

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

from datetime import datetime

from woob.browser.elements import DictElement, ItemElement, method
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import CleanDecimal, Currency, Env, Eval, Format
from woob.browser.pages import JsonPage, LoggedPage, pagination
from woob.capabilities.bill import Bill, Subscription


class LoginPage(JsonPage):
    @property
    def logged(self):
        if self.doc["data"].get("need_double_auth"):
            return False
        return self.doc["result"] == "success"

    @property
    def has_otp(self):
        return self.doc["data"]["default_method"]

    def get_error(self):
        return self.doc["error"]["description"]


class SubscriptionsPage(LoggedPage, JsonPage):
    @method
    class get_subscription(ItemElement):
        klass = Subscription

        obj_id = Eval(str, Dict("data/current_account_id"))
        obj_subscriber = Dict("data/display_name")
        obj_label = Dict("data/display_name")


class DocumentsPage(LoggedPage, JsonPage):
    @pagination
    @method
    class iter_documents(DictElement):
        item_xpath = "data"

        def next_page(self):
            doc = self.page.doc
            current_page = int(doc["page"])
            if current_page >= doc["pages"]:
                return

            params = {
                "ajax": "true",
                "order_by": "name",
                "order_for[name]": "asc",
                "page": current_page + 1,
                "per_page": "100",
            }
            return self.page.browser.documents.build(subid=self.env["subid"], params=params)

        class item(ItemElement):
            klass = Bill

            obj_number = Dict("document/id")
            obj_id = Format("%s_%s", Env("subid"), obj_number)
            obj_date = Eval(datetime.fromtimestamp, Dict("created_at"))
            obj_label = Format("Facture %s", obj_number)
            obj_url = Dict("document/href")
            obj_total_price = CleanDecimal.SI(Dict("amount/amount_incl_tax"))
            obj_currency = Currency(Dict("amount/currency_code"))
            obj_format = "pdf"
