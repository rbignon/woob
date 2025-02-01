# Copyright(C) 2012-2020  Budget Insight
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

import re
from decimal import Decimal

from woob.browser.elements import DictElement, ItemElement, method
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import CleanDecimal, CleanText, Currency, Date, Env, Field, Map, Regexp, Title
from woob.browser.pages import HTMLPage, JsonPage, LoggedPage, RawPage, XMLPage
from woob.capabilities.bank import Account
from woob.capabilities.bank.wealth import Investment, MarketOrder, MarketOrderDirection, MarketOrderType
from woob.capabilities.base import NotAvailable, empty
from woob.tools.capabilities.bank.investments import IsinCode, is_isin_valid
from woob.tools.capabilities.bank.transactions import FrenchTransaction


def float_to_decimal(f):
    return Decimal(str(f))


class MaintenancePage(HTMLPage):
    pass


class LoginPage(JsonPage):
    def has_2fa(self):
        return Dict("statusText", default="")(self.doc) == "totpNeeded"

    def get_session_id(self):
        return Dict("sessionId")(self.doc)

    def get_information(self, information):
        key = "data/" + information
        return Dict(key, default=None)(self.doc)


class OtpPage(RawPage):
    pass


def list_to_dict(l):
    return {d["name"]: d.get("value") for d in l}


# Specific currencies are displayed with a factor
# in the API so we must divide the invest valuations
SPECIFIC_CURRENCIES = {
    "JPY": 100,
}


class AccountsPage(LoggedPage, JsonPage):
    @method
    class get_account(ItemElement):
        klass = Account

        # account balance will be filled with the
        # sum of its investments in browser.py

        def obj_id(self):
            return str(self.page.browser.int_account)

        def obj_number(self):
            return str(self.page.browser.int_account)

        def obj_label(self):
            return "%s DEGIRO" % self.page.browser.name.title()

        def obj_type(self):
            return Account.TYPE_MARKET

    @method
    class iter_investment(DictElement):
        item_xpath = "portfolio/value"

        class item(ItemElement):
            klass = Investment

            def condition(self):
                return float_to_decimal(list_to_dict(self.el["value"])["size"])

            obj_unitvalue = Env("unitvalue", default=NotAvailable)
            obj_unitprice = Env("unitprice", default=NotAvailable)
            obj_original_currency = Env("original_currency", default=NotAvailable)
            obj_original_unitvalue = Env("original_unitvalue", default=NotAvailable)
            obj_original_unitprice = Env("original_unitprice", default=NotAvailable)
            obj_valuation = Env("valuation")
            obj_quantity = Env("quantity", default=NotAvailable)
            obj_diff = Env("diff")
            obj_diff_ratio = Env("diff_ratio", default=NotAvailable)

            def obj__product_id(self):
                return str(list_to_dict(self.el["value"])["id"])

            def obj_label(self):
                product_data = Field("_product_data")(self)
                return product_data["name"]

            def obj_vdate(self):
                product_data = Field("_product_data")(self)
                vdate = product_data.get(
                    "closePriceDate"
                )  # .get() because certain invest don't have that key in the json
                if vdate:
                    return Date().filter(vdate)
                return NotAvailable

            def obj_code(self):
                product_data = Field("_product_data")(self)
                if "isin" not in product_data:
                    return NotAvailable

                code = product_data["isin"]
                if is_isin_valid(code):
                    # Prefix CFD (Contrats for difference) ISIN codes with "XX-"
                    # to avoid id_security duplicates in the database
                    if "- CFD" in Field("label")(self):
                        return "XX-" + code
                    return code
                return NotAvailable

            def obj_code_type(self):
                if empty(Field("code")(self)):
                    return NotAvailable
                return Investment.CODE_TYPE_ISIN

            def obj__product_data(self):
                return self.page.browser.get_product(str(Field("_product_id")(self)))

            def obj_stock_symbol(self):
                product_data = Field("_product_data")(self)
                return CleanText(default=NotAvailable).filter(product_data.get("symbol"))

            def obj_stock_market(self):
                exchanges = Env("exchanges")(self)
                product_data = Field("_product_data")(self)
                if "exchangeId" not in product_data:
                    return NotAvailable
                exchange_id = product_data["exchangeId"]
                if exchange_id:
                    return exchanges.get(int(exchange_id), NotAvailable)
                return NotAvailable

            def parse(self, el):
                product_data = Field("_product_data")(self)
                currency = product_data["currency"]
                unitvalue = Decimal.quantize(Decimal(list_to_dict(Dict("value")(el))["price"]), Decimal("0.0001"))
                unitprice = Decimal.quantize(
                    Decimal(list_to_dict(Dict("value")(el))["breakEvenPrice"]), Decimal("0.0001")
                )
                quantity = Decimal.quantize(Decimal(list_to_dict(Dict("value")(el))["size"]), Decimal("0.01"))
                valuation = Decimal(list_to_dict(Dict("value")(el))["value"])

                invested_amount = Decimal(list_to_dict(Dict("value")(el))["plBase"][self.env["currency"]])
                current_valuation = Decimal(list_to_dict(Dict("value")(el))["todayPlBase"][self.env["currency"]])
                self.env["diff"] = Decimal.quantize(
                    invested_amount - current_valuation,
                    Decimal("0.0001"),
                )
                if invested_amount:
                    # invested amount can be 0
                    self.env["diff_ratio"] = Decimal.quantize(
                        self.env["diff"] / abs(invested_amount), Decimal("0.0001")
                    )

                if currency == "GBX":
                    # Some stocks are priced in GBX (penny sterling)
                    # We convert them to GBP to avoid ambiguity with the crypto-currency with the same symbol
                    currency = "GBP"
                    unitvalue = unitvalue / 100
                    unitprice = unitprice / 100

                self.env["valuation"] = round(valuation / SPECIFIC_CURRENCIES.get(currency, 1), 2)
                self.env["quantity"] = quantity

                if currency == self.env["currency"]:
                    self.env["unitvalue"] = unitvalue
                    self.env["unitprice"] = unitprice
                else:
                    self.env["original_unitvalue"] = unitvalue
                    self.env["original_unitprice"] = unitprice

                self.env["original_currency"] = currency


class AccountDetailsPage(LoggedPage, XMLPage):
    def get_currency(self):
        base_currency = self.doc.xpath("//baseCurrency")
        if base_currency:
            return base_currency[0].text
        else:
            raise ValueError("baseCurrency not found in XML response.")


class InvestmentPage(LoggedPage, JsonPage):
    def get_products(self):
        return self.doc.get("data", [])


MARKET_ORDER_TYPES = {
    0: MarketOrderType.LIMIT,
    1: MarketOrderType.MARKET,
    2: MarketOrderType.MARKET,
    3: MarketOrderType.MARKET,
}

MARKET_ORDER_DIRECTIONS = {
    "B": MarketOrderDirection.BUY,
    "S": MarketOrderDirection.SALE,
}


class MarketOrdersPage(LoggedPage, JsonPage):
    @method
    class iter_market_orders(DictElement):
        item_xpath = "data"
        ignore_duplicate = True

        class item(ItemElement):
            klass = MarketOrder

            obj_id = Dict("orderId", default=None)
            obj_quantity = CleanDecimal.SI(Dict("size"))
            obj_date = Date(CleanText(Dict("created")))
            obj_state = Title(Dict("status"))
            obj__product_id = CleanText(Dict("productId"))
            obj_direction = Map(CleanText(Dict("buysell")), MARKET_ORDER_DIRECTIONS, MarketOrderDirection.UNKNOWN)
            obj_order_type = Map(Dict("orderTypeId"), MARKET_ORDER_TYPES, MarketOrderType.UNKNOWN)

            def obj_ordervalue(self):
                if Dict("orderTypeId")(self) != 0:
                    # Not applicable
                    return NotAvailable
                return CleanDecimal.SI(Dict("price"))(self)

            # Some information is not available in this JSON
            # so we fetch it in the 'products' dictionary.
            # There is no info regarding unitprice, unitvalue & payment method.
            def _product(self):
                return self.page.browser.get_product(str(Field("_product_id")(self)))

            def obj_label(self):
                return self._product()["name"]

            def obj_currency(self):
                return Currency().filter(self._product()["currency"])

            def obj_code(self):
                return IsinCode(default=NotAvailable).filter(self._product()["isin"])

            def obj_stock_symbol(self):
                return CleanText(default=NotAvailable).filter(self._product().get("symbol"))

            def obj_stock_market(self):
                exchanges = Env("exchanges")(self)
                exchange_id = self._product()["exchangeId"]
                if exchange_id:
                    return exchanges.get(int(exchange_id), NotAvailable)
                return NotAvailable

            def validate(self, obj):
                # Some rejected orders do not have an ID, we skip them
                return obj.id


class Transaction(FrenchTransaction):
    PATTERNS = [
        (re.compile("^(Deposit|Versement)"), FrenchTransaction.TYPE_DEPOSIT),
        (re.compile("^(Buy|Sell|Achat|Vente)"), FrenchTransaction.TYPE_ORDER),
        (re.compile("^(?P<text>.*)"), FrenchTransaction.TYPE_BANK),
    ]


class HistoryPage(LoggedPage, JsonPage):
    @method
    class iter_history(DictElement):
        def find_elements(self):
            return self.el.get("data", {}).get("cashMovements", [])

        class item(ItemElement):
            klass = Transaction

            def condition(self):
                # Transactions without amount are ignored even on the website
                return Dict("change", default=None)(self)

            obj_raw = Transaction.Raw(CleanText(Dict("description")))
            obj_date = Date(CleanText(Dict("date")))
            obj__isin = Regexp(Dict("description"), r"\((.{12}?)\)", nth=-1, default=None)
            obj__number = Regexp(
                Dict("description"), r"^([Aa]chat|[Vv]ente|[Bb]uy|[Ss]ell) (\d+[,.]?\d*)", template="\\2", default=None
            )
            obj__datetime = Dict("date")

            def obj__action(self):
                if not Field("_isin")(self):
                    return

                label = Field("raw")(self).split()[0]
                labels = {
                    "Buy": "B",
                    "Achat": "B",
                    "Compra": "B",
                    "Kauf": "B",
                    "Sell": "S",
                    "Vente": "S",
                    "Venta": "S",
                    "Venda": "S",
                    "Verkauf": "S",
                    "Taxe": None,
                    "Frais": None,
                    "Intérêts": None,
                    "Comisión": None,
                    "Custo": None,
                    "Einrichtung": None,
                    "DEGIRO": None,
                    "TAKE": None,
                    "STOCK": None,
                    "SUBSCRIPTION": None,
                    "REDEEMED": None,
                    "ISIN": None,
                    "MERGER:": None,
                    "EXPIRATION": None,
                    "SETTLEMENT": None,
                    "ASSIGNMENT": None,
                    "ON": None,
                    # make sure we don't miss transactions labels specifying an ISIN
                }
                if label not in labels:
                    self.logger.warning("Unknown action label: %s", label)
                return labels.get(label)

            def obj_amount(self):
                if Env("account_currency")(self) == Dict("currency")(self):
                    return float_to_decimal(Dict("change")(self))
                # The amount is not displayed so we only retrieve the original_amount
                return NotAvailable

            def obj_original_amount(self):
                if Env("account_currency")(self) == Dict("currency")(self):
                    return NotAvailable
                return float_to_decimal(Dict("change")(self))

            def obj_original_currency(self):
                if Env("account_currency")(self) == Dict("currency")(self):
                    return NotAvailable
                return Currency(Dict("currency"))(self)

            def obj_investments(self):
                tr_investment_list = Env("transaction_investments")(self).v
                isin = Field("_isin")(self)
                action = Field("_action")(self)
                if isin and action:
                    tr_inv_key = (isin, action, Field("_datetime")(self))
                    try:
                        return [tr_investment_list[tr_inv_key]]
                    except KeyError:
                        pass
                return []

            def validate(self, obj):
                assert not empty(obj.amount) or not empty(
                    obj.original_amount
                ), "This transaction has no amount and no original_amount!"
                return True

    @method
    class iter_transaction_investments(DictElement):
        item_xpath = "data"

        class item(ItemElement):
            klass = Investment

            obj__product_id = Dict("productId")
            obj_quantity = CleanDecimal(Dict("quantity"))
            obj_unitvalue = CleanDecimal(Dict("price"))
            obj_vdate = Date(CleanText(Dict("date")))
            obj__action = Dict("buysell")
            obj__datetime = Dict("date")

            def _product(self):
                return self.page.browser.get_product(str(Field("_product_id")(self)))

            def obj_label(self):
                return self._product()["name"]

            def obj_code(self):
                code = self._product()["isin"]
                if is_isin_valid(code):
                    # Prefix CFD (Contrats for difference) ISIN codes with "XX-"
                    # to avoid id_security duplicates in the database
                    if "- CFD" in Field("label")(self):
                        return "XX-" + code
                    return code
                return NotAvailable

            def obj_code_type(self):
                if empty(Field("code")(self)):
                    return NotAvailable
                return Investment.CODE_TYPE_ISIN

    def get_products(self):
        return {d["productId"] for d in self.doc["data"]}


class ExchangesPage(JsonPage):
    def get_stock_market_exchanges(self):
        exchanges = {}
        for exchange in self.doc["exchanges"]:
            market_code = exchange.get("code")
            if market_code:
                exchanges[exchange["id"]] = market_code

        assert exchanges, "Could not fetch stock market exchanges"
        return exchanges
