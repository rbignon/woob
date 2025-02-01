# -*- coding: utf-8 -*-

# Copyright(C) 2010-2011 Vincent Paredes
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

import re
from datetime import datetime
from urllib.parse import parse_qsl, urlencode, urlparse

from woob.browser.elements import DictElement, ItemElement, ListElement, method
from woob.browser.filters.html import HasElement, Link
from woob.browser.filters.javascript import JSValue
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import (
    BrowserURL,
    CleanDecimal,
    CleanText,
    Date,
    Env,
    Eval,
    Field,
    Format,
    Lower,
    Regexp,
)
from woob.browser.pages import HTMLPage, JsonPage, LoggedPage, pagination
from woob.capabilities.base import NotAvailable
from woob.capabilities.bill import Bill, Subscription


FRENCH_MONTHS = (
    "janv.",
    "févr.",
    "mars",
    "avr.",
    "mai",
    "juin",
    "juil.",
    "août",
    "sept.",
    "oct.",
    "nov.",
    "déc.",
)


class BillsApiProPage(LoggedPage, JsonPage):
    def build_doc(self, content):
        if not content:
            return {"bills": []}  # No bills
        return super(BillsApiProPage, self).build_doc(content)

    @method
    class get_bills(DictElement):
        item_xpath = "bills"
        # orange's API will sometimes return the temporary bill for the current month along with other bills
        # in the json. The url will lead to the exact same document, this is probably not intended behaviour and
        # causes woob to raise a DataError as they'll have identical ids.
        ignore_duplicate = True

        class item(ItemElement):
            klass = Bill

            obj_date = Date(Dict("dueDate"), default=NotAvailable)
            obj_total_price = CleanDecimal.SI(Dict("amountIncludingTax"))
            obj_format = "pdf"

            def obj_label(self):
                return "Facture du %s" % Field("date")(self)

            def obj_id(self):
                return "%s_%s" % (Env("subid")(self), Field("date")(self).strftime("%d%m%Y"))

            def get_params(self):
                params = {
                    "billId": Dict("id")(self) or "",
                    "billDate": Dict("dueDate")(self),
                    "billFreeDuty": Dict("amountExcludingTax")(self),
                    "billDuty": Dict("amountIncludingTax")(self),
                }
                return urlencode(params)

            def get_bill_name(self):
                # Date must be formatted like "juin 2023" or "avr. 2023".
                due_date = datetime.fromisoformat(Dict("dueDate")(self)).date()
                return f"Facture Orange {FRENCH_MONTHS[due_date.month - 1]} {due_date.year}"

            obj_url = BrowserURL(
                "doc_api_pro",
                subid=Env("subid"),
                dir=Dict("documents/0/mainDir"),
                fact_type=Dict("documents/0/subDir"),
                bill_name=get_bill_name,
                bill_params=get_params,
            )
            obj__is_v2 = False


class BillsApiParPage(LoggedPage, JsonPage):
    def build_doc(self, content):
        if not content:
            return {"billsHistory": {"billList": []}}  # No bills
        return super(BillsApiParPage, self).build_doc(content)

    @method
    class get_bills(DictElement):
        item_xpath = "billsHistory/billList"

        def condition(self):
            return Dict("billsHistory", default=None)(self) and Dict("billsHistory/billList", default=None)(self)

        class item(ItemElement):
            klass = Bill

            obj_date = Date(Dict("date"), default=NotAvailable)
            obj_total_price = Eval(lambda x: x / 100, CleanDecimal(Dict("amount")))
            obj_format = "pdf"

            def obj_label(self):
                return "Facture du %s" % Field("date")(self)

            def obj_id(self):
                return "%s_%s" % (Env("subid")(self), Field("date")(self).strftime("%d%m%Y"))

            obj_url = Format("%s%s", BrowserURL("doc_api_par"), Dict("hrefPdf"))
            obj__is_v2 = True


class BillsApiProRechargeablePage(LoggedPage, JsonPage):
    @method
    class get_bills(DictElement):
        item_xpath = "billList"

        class item(ItemElement):
            klass = Bill

            obj_date = Date(CleanText(Dict("date")))
            obj_duedate = Date(CleanText(Dict("dueDate"), default=None), default=None)
            obj_label = CleanText(Dict("title"))
            obj_total_price = CleanDecimal.SI(Dict("priceTTC"))
            obj_pre_tax_price = CleanDecimal.SI(Dict("priceHT"))
            obj_startdate = Date(CleanText(Dict("startDate")))
            obj_finishdate = Date(CleanText(Dict("endDate")))
            obj__download_link = CleanText(Dict("downloadLink"), default=None)
            obj_id = Format("%s_%s", Env("subid"), CleanText(Dict("id")))

            # Always `False` if the user is not the account manager
            # or the CEO of his company
            obj_has_file = HasElement(Field("_download_link"))


class SubscriptionsPage(LoggedPage, HTMLPage):
    def build_doc(self, data):
        data = data.decode(self.encoding)
        for line in data.split("\n"):
            mtc = re.match(r"necFe.bandeau.container.innerHTML\s*=\s*stripslashes\((.*)\);$", line)
            if mtc:
                html = JSValue().filter(mtc.group(1)).encode(self.encoding)
                return super(SubscriptionsPage, self).build_doc(html)

    @method
    class iter_subscription(ListElement):
        item_xpath = '//ul[@id="contractContainer"]//a[starts-with(@id,"carrousel-")]'

        class item(ItemElement):
            klass = Subscription

            obj_id = Regexp(Link("."), r"\bidContrat=(\d+)", default="")
            obj__page = Regexp(Link("."), r"\bpage=([^&]+)", default="")
            obj_label = CleanText(".")
            obj__is_pro = False

            def validate(self, obj):
                # unsubscripted contracts may still be there, skip them else
                # facture-historique could yield wrong bills
                return bool(obj.id) and obj._page != "nec-tdb-ouvert"


class SubscriptionsApiPage(LoggedPage, JsonPage):
    @method
    class iter_subscription(DictElement):
        item_xpath = "contracts"

        class item(ItemElement):
            klass = Subscription

            obj_id = Dict("contractId")
            obj_label = Dict("offerName")
            obj__is_pro = False


class ContractsPage(LoggedPage, JsonPage):
    @pagination
    @method
    class iter_subscriptions(DictElement):
        item_xpath = "contracts"

        def next_page(self):
            params = dict(parse_qsl(urlparse(self.page.url).query))
            page_number = int(params["page"])
            nbcontractsbypage = int(params["nbcontractsbypage"])
            nb_subs = page_number * nbcontractsbypage

            # sometimes totalContracts can be different from real quantity
            # already seen totalContracts=39 with 38 contracts in json
            # so we compare nb contracts received in this response with number per page to make sure we stop
            # even if there is oneday totalContracts=7677657689 but just 8 contracts
            doc = self.page.doc
            if nb_subs < doc["totalContracts"] and len(doc["contracts"]) == nbcontractsbypage:
                params["page"] = page_number + 1
                return self.page.browser.contracts.build(params=params)

        class item(ItemElement):
            klass = Subscription

            obj_id = Dict("id")
            obj_label = Format("%s %s", Dict("name"), Dict("mainLine"))
            obj__from_api = False

            def condition(self):
                return Dict("status")(self) == "OK"

            def obj__is_pro(self):
                return Dict("offerNature")(self) == "PROFESSIONAL"


class ContractsApiPage(LoggedPage, JsonPage):
    @method
    class iter_subscriptions(DictElement):
        item_xpath = "contracts"

        class item(ItemElement):
            klass = Subscription

            obj_id = CleanText(Dict("cid"))
            obj_label = Dict("offerName")

            def obj_subscriber(self):
                names = (
                    CleanText(Dict("holder/firstName", default=""))(self),
                    CleanText(Dict("holder/lastName", default=""))(self),
                )
                if not any(names):
                    return NotAvailable
                return " ".join([n for n in names if n])

            def obj__is_pro(self):
                return Dict("telco/marketType", default="PAR")(self) == "PRO"

            obj__from_api = True

            def condition(self):
                return Lower(Dict("status"))(self) == "actif"
