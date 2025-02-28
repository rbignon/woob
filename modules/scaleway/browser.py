# Copyright(C) 2022      Jeremy Demange (scrapfast.io)
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

import base64
import decimal
from datetime import datetime

import requests

from woob.browser import URL, LoginBrowser, StatesMixin
from woob.capabilities.bill import Bill, Subscription


class ScalewayBrowser(LoginBrowser, StatesMixin):
    BASEURL = "https://api.scaleway.com"
    TIMEOUT = 60

    login = URL(r"/account/v1/jwt")
    apikey = URL(r"iam/v1alpha1/api-keys/(?P<accessKey>*)")
    invoices = URL(r"/billing/v2beta1/invoices\?page=1&per_page=10")

    def __init__(self, config, *args, **kwargs):
        super().__init__("login", "password", *args, **kwargs)
        self.config = config
        self.access_key = self.config["access_key"].get()
        self.secret_key = self.config["secret_key"].get()

    def build_request(self, *args, **kwargs) -> requests.Request:
        kwargs.setdefault("headers", {})["X-Auth-Token"] = self.secret_key
        return super().build_request(*args, **kwargs)

    def get_subscription_list(self):
        # self.profile.go(idAccount=self.idaccount)
        self.apikey.go(accessKey=self.access_key)
        result = self.response.json()
        sub = Subscription()
        sub.id = result["access_key"]
        sub.subscriber = sub.label = result["description"]
        yield sub

    def iter_documents(self, subscription=""):
        self.invoices.go()
        result = self.response.json()
        for invoice in result["invoices"]:
            if invoice["state"] in ["draft", "outdated"]:
                continue
            ctx = decimal.getcontext()
            decimal.getcontext().prec = 6
            bouleEt = Bill()
            bouleEt.currency = invoice["total_taxed"]["currency_code"]
            bouleEt.startdate = datetime.fromisoformat(invoice["start_date"])
            bouleEt.finishdate = datetime.fromisoformat(invoice["stop_date"])
            bouleEt.duedate = datetime.fromisoformat(invoice["due_date"])
            bouleEt.date = datetime.fromisoformat(invoice["issued_date"])
            bouleEt.id = invoice["id"]
            # Cf https://pkg.go.dev/github.com/scaleway/scaleway-sdk-go/scw#Money for detail on expressing amounts
            # NB: using `decimal` to remove rounding errors etc...
            bouleEt.total_price = decimal.Decimal(invoice["total_taxed"]["units"]) + decimal.Decimal(
                invoice["total_taxed"]["nanos"]
            ) / decimal.Decimal("1000000000")
            bouleEt.vat = decimal.Decimal(invoice["total_tax"]["units"]) + decimal.Decimal(
                invoice["total_tax"]["nanos"]
            ) / decimal.Decimal("1000000000")
            bouleEt.pre_tax_price = decimal.Decimal(invoice["total_untaxed"]["units"]) + decimal.Decimal(
                invoice["total_untaxed"]["nanos"]
            ) / decimal.Decimal("1000000000")
            bouleEt.url = f"https://api.scaleway.com/billing/v2beta1/invoices/{bouleEt.id}/download"
            bouleEt.format = "pdf"
            bouleEt.label = "{} invoice {} #{} - {} - {}".format(
                bouleEt.date.strftime("%Y%m%d"),
                invoice["seller_name"],
                invoice["number"],
                invoice["organization_name"],
                bouleEt.startdate.strftime("%Y-%m"),
            )
            decimal.setcontext(ctx)
            yield bouleEt

    def download_document(self, document):
        json_doc = self.open(document.url).json()
        b64_content = json_doc.get("content", None)
        content = None
        if b64_content:
            content = base64.b64decode(b64_content)
        return content
