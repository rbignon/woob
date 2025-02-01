# Copyright(C) 2018      Vincent A
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

from decimal import Decimal

from woob.browser.elements import DictElement, ItemElement, method
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import CleanText, Eval, Regexp
from woob.browser.pages import JsonPage, LoggedPage, PartialHTMLPage
from woob.capabilities.bank import Account


def float_to_decimal(v):
    return Decimal(str(v))


class HtmlLoginFragment(PartialHTMLPage):
    def get_recaptcha_site_key(self):
        return Regexp(CleanText('//script[contains(text(), "sitekey")]/text()'), r'"sitekey" *: *"([^"]*)"')(self.doc)


class LoginPage(JsonPage):
    def get_token(self):
        return self.doc["detail"]["token"]


class AccountsPage(LoggedPage, JsonPage):
    ENCODING = "utf-8"  # chardet is shit

    @method
    class iter_accounts(DictElement):
        item_xpath = "detail"

        class item(ItemElement):
            klass = Account

            obj_id = Eval(str, Dict("id"))
            obj_label = Dict("name")
            obj_balance = Eval(float_to_decimal, Dict("current_value"))
            obj_valuation_diff = Eval(float_to_decimal, Dict("absolute_performance"))
            obj_currency = "EUR"
            obj_type = Account.TYPE_LIFE_INSURANCE


class AccountPage(LoggedPage, JsonPage):
    def get_invest_key(self):
        return self.doc["detail"]["project_kind"], self.doc["detail"]["risk_level"]

    def get_kind(self):
        return self.doc["detail"]["project_kind"]

    def get_risk(self):
        return self.doc["detail"]["risk_level"]


class HistoryPage(LoggedPage, JsonPage):
    pass


# using site labels
ASSET_TYPE = {
    "risky": "Actions",
    "risk_free": "Obligations",
    "guaranteed": "Fonds à capital garanti",
}


class InvestPage(LoggedPage, JsonPage):
    ENCODING = "utf-8"

    def get_invest(self, kind, risk):
        for pk in self.doc["portfolios"]:
            if pk["kind"] == kind:
                break
        else:
            assert False

        for p in pk["target_portfolios"]:
            if p["risk_id"] == risk:
                break
        else:
            assert False

        for line in p["lines"]:
            yield {
                "isin": line["isin"],
                "name": line["name"],
                "share": float_to_decimal(line["weight"]) / 100,
                "asset_type": ASSET_TYPE[line["risk_type"]],
            }
