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

# flake8: compatible

import re
from urllib.parse import parse_qs

import requests

from woob.browser.elements import DictElement, ItemElement, TableElement, method
from woob.browser.filters.html import Attr, Link, TableCell
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import (
    Base,
    CleanDecimal,
    CleanText,
    Coalesce,
    Currency,
    Date,
    Env,
    Eval,
    Field,
    Format,
    Lower,
    Map,
    MapIn,
    Regexp,
)
from woob.browser.pages import HTMLPage, JsonPage, LoggedPage, pagination
from woob.capabilities.bank import Account, AccountOwnership, AccountOwnerType, Loan
from woob.capabilities.bank.wealth import Investment
from woob.capabilities.base import NotAvailable
from woob.capabilities.profile import Person
from woob.tools.capabilities.bank.investments import IsinCode, IsinType, create_french_liquidity
from woob.tools.capabilities.bank.transactions import FrenchTransaction


class ProfilePage(LoggedPage, JsonPage):
    @method
    class get_profile(ItemElement):
        klass = Person

        obj_id = Coalesce(
            Dict("infoCapaciteJuridique/identifiantBF", default=NotAvailable),
            Dict("login", default=NotAvailable),
        )
        obj_name = Format("%s %s", Dict("infoCivilite/prenom"), Dict("infoCivilite/nom"))
        obj_firstname = Dict("infoCivilite/prenom")
        obj_lastname = Dict("infoCivilite/nom")

        def obj_email(self):
            for info in self.el["contacts"]:
                if info["type"] == "MAIL":
                    return Dict("value")(info)
            # can be unavailable on pro website for example
            return NotAvailable


ACCOUNT_TYPES = {
    "compte courant": Account.TYPE_CHECKING,
    "compte cheque": Account.TYPE_CHECKING,
    "compte basique": Account.TYPE_CHECKING,
    "livret": Account.TYPE_SAVINGS,
    "livret d'epargne": Account.TYPE_SAVINGS,
    "compte a terme": Account.TYPE_SAVINGS,
    "compte titres": Account.TYPE_MARKET,
    "epargne en actions": Account.TYPE_PEA,
    "plan d'epargne en actions": Account.TYPE_PEA,
    "invest4life": Account.TYPE_LIFE_INSURANCE,
    "alz ret": Account.TYPE_LIFE_INSURANCE,
    "retraite": Account.TYPE_LIFE_INSURANCE,
    "ideavie": Account.TYPE_LIFE_INSURANCE,
    "assurance-vie": Account.TYPE_LIFE_INSURANCE,
    "agf itineraires": Account.TYPE_LIFE_INSURANCE,
}

ACCOUNT_OWNERSHIPS = {
    "TIT": AccountOwnership.OWNER,
    "COT": AccountOwnership.CO_OWNER,
}

ACCOUNT_OWNERTYPES = {
    "PRIV": AccountOwnerType.PRIVATE,
}

COMINGS_TYPES = {
    "PRLV": FrenchTransaction.TYPE_ORDER,
    "CARTE": FrenchTransaction.TYPE_DEFERRED_CARD,
    "CREDI": FrenchTransaction.TYPE_LOAN_PAYMENT,
}


class Transaction(FrenchTransaction):
    PATTERNS = [
        (re.compile(r"^CARTE (?P<dd>\d{2})/(?P<mm>\d{2}) (?P<text>.*)"), FrenchTransaction.TYPE_CARD),
        (re.compile(r"^(?P<text>(PRLV|PRELEVEMENTS).*)"), FrenchTransaction.TYPE_ORDER),
        (re.compile(r"^(?P<text>RET DAB.*)"), FrenchTransaction.TYPE_WITHDRAWAL),
        (re.compile(r"^(?P<text>ECH.*)"), FrenchTransaction.TYPE_LOAN_PAYMENT),
        (re.compile(r"^(?P<text>VIR.*)"), FrenchTransaction.TYPE_TRANSFER),
        (re.compile(r"^(?P<text>ANN.*)"), FrenchTransaction.TYPE_PAYBACK),
        (re.compile(r"^(?P<text>(VRST|VERSEMENT).*)"), FrenchTransaction.TYPE_DEPOSIT),
        (re.compile(r"^(?P<text>CHQ.*)"), FrenchTransaction.TYPE_CHECK),
        (re.compile(r"^(?P<text>.*)"), FrenchTransaction.TYPE_BANK),
    ]


class AccountsPage(LoggedPage, JsonPage):
    @method
    class iter_accounts(DictElement):
        class item(ItemElement):
            klass = Account

            obj_id = Dict("accountId")
            obj_number = Dict("sourceContractId")
            obj_label = Dict("label")

            obj_type = MapIn(
                Lower(Dict("label")),
                ACCOUNT_TYPES,
                Account.TYPE_UNKNOWN,
            )

            obj_ownership = Map(
                Dict("personRole"),
                ACCOUNT_OWNERSHIPS,
                NotAvailable,
            )

            obj_owner_type = Map(
                Dict("usage"),
                ACCOUNT_OWNERTYPES,
                NotAvailable,
            )

            # IBAN is obfuscated
            obj_iban = NotAvailable

            def validate(self, obj):
                # life insurances visible on the website are found on ContractsPage
                return obj.type != Account.TYPE_LIFE_INSURANCE

    def fill_balance(self, account):
        balance = next(bal for bal in self.doc if bal["balanceType"] in ("WEB", "VALO"))
        account.balance = CleanDecimal.US(Dict("balanceAmount/amount"))(balance)
        account.currency = Currency(Dict("balanceAmount/currency"))(balance)

    def fill_coming(self, account):
        account.coming = CleanDecimal.US(Dict("all"))(self.doc)

    @method
    class iter_transactions(DictElement):
        class item(ItemElement):
            klass = Transaction

            obj_id = Dict("id")
            obj_amount = CleanDecimal.SI(Dict("amount"))
            obj_date = Date(Dict("bookedDate"))
            obj_rdate = Date(Dict("transactionDate"))
            obj_vdate = Date(Dict("valueDate"))
            obj_raw = Transaction.Raw(Dict("label"))

    @method
    class iter_comings(DictElement):
        class item(ItemElement):
            klass = Transaction

            obj_amount = CleanDecimal.SI(Dict("amount"))
            obj_date = Date(Dict("expectedDate"))
            obj_rdate = Date(Dict("purchaseDate", default=None), default=NotAvailable)
            obj_label = Dict("label")
            obj_type = Map(
                Dict("family"),
                COMINGS_TYPES,
                FrenchTransaction.TYPE_UNKNOWN,
            )


class ContractsPage(LoggedPage, JsonPage):
    @method
    class get_contract(ItemElement):
        klass = Account

        def condition(self):
            return Dict("lifeInsuranceDetails/lifeContract", default=None)(self)

        obj_id = obj_number = Dict("lifeInsuranceDetails/contractNumber")
        obj_label = Format(
            "%s n°%s",
            Dict("lifeInsuranceDetails/contractLabel"),
            Dict("lifeInsuranceDetails/contractNumber"),
        )
        obj_balance = Coalesce(
            CleanDecimal.French(
                Dict("lifeInsuranceDetails/lifeContract/constitutedCapital", default=None), default=NotAvailable
            ),
            CleanDecimal.French(
                Dict("lifeInsuranceDetails/contingencyContract/deathCapital", default=None), default=NotAvailable
            ),
        )
        obj_currency = "EUR"
        obj_type = Account.TYPE_LIFE_INSURANCE


class LoansPage(LoggedPage, JsonPage):
    def build_doc(self, content):
        if self.response.status_code == 204:
            # empty json if no content
            self.logger.warning("JSON has no content")
            return list()
        return super().build_doc(content)

    @method
    class iter_loans(DictElement):
        class item(ItemElement):
            klass = Loan

            obj_id = obj_number = Dict("id")
            obj_label = Dict("usage")
            obj_balance = CleanDecimal.SI(Dict("outstandingBalance"), sign="-")
            obj_currency = "EUR"
            obj_type = Account.TYPE_LOAN
            obj_total_amount = CleanDecimal.SI(Dict("initialAmount"))
            obj_next_payment_amount = CleanDecimal.SI(Dict("amountNextTerm"))
            obj_next_payment_date = Date(Dict("dateNextTerm"))
            obj_maturity_date = Date(Dict("endOfLoanDate"))
            obj_duration = Eval(int, CleanDecimal(Dict("duration")))

            def obj_ownership(self):
                owner = Format("%s %s", Dict("firstNameBorrower"), Dict("lastNameBorrower"))(self)
                if all(n in owner.upper().split() for n in self.env["name"].split()):
                    return AccountOwnership.OWNER
                return AccountOwnership.CO_OWNER


class CypherPage(LoggedPage, JsonPage):
    def get_cypher(self):
        return Dict("cypher")(self.doc)


class MarketPage(LoggedPage, HTMLPage):
    pass


class InvestmentsPage(LoggedPage, HTMLPage):
    def get_vdate(self):
        return CleanText('//th[contains(text(), "Valorisation au ")]')(self.doc).split()[-1]

    class GenericPagination:
        def next_page(self):
            select_js_handler = Attr('//div[@id="turn_next"]//a', "onclick")
            params = Regexp(select_js_handler, r'href: ".*\?(.*)"')(self.page.doc)
            params = parse_qs(params)
            url = self.page.url.split("?")[0]
            return requests.Request("POST", url, params=params)

    @pagination
    @method
    class iter_investment(TableElement):
        item_xpath = '//table[@id="valuation"]/tbody/tr'
        head_xpath = '//table[@id="valuation"]/thead//th'

        col_label = "Libellé"
        col_quantity = "Qté"
        col_unitprice = "P.U."
        col_unitvalue = "Cours"
        col_valuation = "Valo"
        col_diff = "+/- lat."

        class item(ItemElement):
            klass = Investment

            def condition(self):
                return CleanText(".")(self) != "Aucun élément à afficher."

            obj_label = Base(TableCell("label"), CleanText(".//a"))
            obj_code = Base(
                TableCell("label"),
                IsinCode(Regexp(Link(".//a", default=""), r"isin=([^&]+)", default=""), default=NotAvailable),
            )
            obj_code_type = Base(
                TableCell("label"), IsinType(Regexp(Link(".//a", default=""), r"isin=([^&]+)", default=""))
            )
            obj_quantity = CleanDecimal.French(TableCell("quantity"), default=NotAvailable)
            obj_unitprice = CleanDecimal.French(TableCell("unitprice"), default=NotAvailable)
            obj_unitvalue = CleanDecimal.French(TableCell("unitvalue"), default=NotAvailable)
            obj_valuation = CleanDecimal.French(TableCell("valuation"))
            obj_diff = CleanDecimal.French(TableCell("diff"), default=NotAvailable)
            obj_vdate = Date(Env("vdate"), dayfirst=True)

    @pagination
    @method
    class iter_history(TableElement, GenericPagination):
        item_xpath = '//table[@id="histo"]/tbody/tr[not(@class="empty")]'
        head_xpath = '//table[@id="histo"]/thead/tr/th'

        col_date = "Date"
        col_label = "Opération"
        col_amount = "Mt Brut"
        col_labelinv = "Valeur"
        col_quantity = "Qté"

        class item(ItemElement):
            klass = Transaction

            obj_raw = Transaction.Raw(TableCell("label"))
            obj_date = Date(CleanText(TableCell("date")), dayfirst=True)
            obj_amount = CleanDecimal.French(TableCell("amount"))

            def obj_investments(self):
                i = Investment()
                i.label = CleanText().filter(TableCell("labelinv")(self)[0].xpath(".//a"))
                i.code = CleanText().filter(TableCell("labelinv")(self)[0].xpath(".//a"))
                i.quantity = CleanDecimal.French(TableCell("quantity"))(self)
                i.valuation = Field("amount")(self)
                i.vdate = Field("date")(self)
                return [i]

    def get_liquidity(self):
        liquidity_element = self.doc.xpath('//tr[td[contains(text(), "Solde espèces")]]')
        assert len(liquidity_element) <= 1
        if liquidity_element:
            valuation = CleanDecimal.French("./td[2]")(liquidity_element[0])
            return create_french_liquidity(valuation)
