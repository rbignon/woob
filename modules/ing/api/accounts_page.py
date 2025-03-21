# Copyright(C) 2019 Sylvie Ye
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

import re

from woob.browser.elements import DictElement, ItemElement, method
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import CleanDecimal, CleanText, Date, Eval, Field, Format, Lower, Map, MapIn, Upper
from woob.browser.pages import HTMLPage, JsonPage, LoggedPage
from woob.capabilities.bank import Account, AccountOwnership, AccountOwnerType, Investment
from woob.capabilities.base import NotAvailable
from woob.tools.capabilities.bank.investments import IsinCode, IsinType
from woob.tools.capabilities.bank.transactions import FrenchTransaction


class Transaction(FrenchTransaction):
    PATTERNS = [
        (
            re.compile(r"^retrait dab (?P<dd>\d{2})/(?P<mm>\d{2})/(?P<yy>\d{4}) (?P<text>.*)"),
            FrenchTransaction.TYPE_WITHDRAWAL,
        ),
        # Withdrawal in foreign currencies will look like "retrait 123 currency"
        (re.compile(r"^retrait (?P<text>.*)"), FrenchTransaction.TYPE_WITHDRAWAL),
        (
            re.compile(r"^paiement par carte (?P<dd>\d{2})/(?P<mm>\d{2})/(?P<yy>\d{4}) (?P<text>.*)"),
            FrenchTransaction.TYPE_CARD,
        ),
        (re.compile(r"^virement (sepa )?(emis vers|recu|emis)? (?P<text>.*)"), FrenchTransaction.TYPE_TRANSFER),
        (re.compile(r"^remise cheque(?P<text>.*)"), FrenchTransaction.TYPE_DEPOSIT),
        (re.compile(r"^cheque (?P<text>.*)"), FrenchTransaction.TYPE_CHECK),
        (re.compile(r"^prelevement (?P<text>.*)"), FrenchTransaction.TYPE_ORDER),
        (re.compile(r"^prlv sepa (?P<text>.*?) : .*"), FrenchTransaction.TYPE_ORDER),
        (re.compile(r"^prélèvement sepa en faveur de (?P<text>.*)"), FrenchTransaction.TYPE_ORDER),
        (re.compile(r"^commission sur (?P<text>.*)"), FrenchTransaction.TYPE_BANK),
    ]

    TYPES = {
        "PURCHASE_CARD": FrenchTransaction.TYPE_CARD,
        "TRANSFER": FrenchTransaction.TYPE_TRANSFER,
        "SEPA_DEBIT": FrenchTransaction.TYPE_ORDER,
        "CARD_WITHDRAWAL": FrenchTransaction.TYPE_WITHDRAWAL,
        "FEES": FrenchTransaction.TYPE_BANK,
        "CHECK": FrenchTransaction.TYPE_CHECK,
        "OTHER": FrenchTransaction.TYPE_UNKNOWN,
    }


ACCOUNT_TYPES = {
    "Courant": Account.TYPE_CHECKING,
    "Livret A": Account.TYPE_SAVINGS,
    "Orange": Account.TYPE_SAVINGS,
    "Durable": Account.TYPE_SAVINGS,
    "Titres": Account.TYPE_MARKET,
    "PEA": Account.TYPE_PEA,
    "Direct Vie": Account.TYPE_LIFE_INSURANCE,
    "Assurance Vie": Account.TYPE_LIFE_INSURANCE,
    "Crédit Immobilier": Account.TYPE_LOAN,
    "Prêt Personnel": Account.TYPE_LOAN,
    "Plan Epargne Action": Account.TYPE_PEA,
}


class AccountsPage(LoggedPage, JsonPage):
    @method
    class iter_accounts(DictElement):
        item_xpath = "accounts"

        class item(ItemElement):
            klass = Account

            obj_id = obj__uid = Dict("uid")
            obj_label = Dict("type/label")
            obj_type = MapIn(Dict("type/label"), ACCOUNT_TYPES, Account.TYPE_UNKNOWN)
            obj_number = CleanText(Dict("label"), replace=[(" ", "")])
            obj_owner_type = AccountOwnerType.PRIVATE

            def obj_balance(self):
                # ledgerBalance=-X and hasPositiveBalance=false -> negative balance (checking account)
                # ledgerBalance=+X and hasPositiveBalance=false -> negative balance (due mortgage)

                if not Dict("hasPositiveBalance")(self):
                    return CleanDecimal(Dict("ledgerBalance"), sign="-")(self)
                return CleanDecimal(Dict("ledgerBalance"), sign="+")(self)

            obj_currency = "EUR"  # no currency info in api! we assume there's only EUR then

            def obj_ownership(self):
                ownership = Dict("ownership/code", default=None)(self)
                role = Dict("role/label", default=None)(self)

                if ownership == "JOINT":
                    return AccountOwnership.CO_OWNER
                elif ownership == "SINGLE":
                    if role == "Titulaire":
                        return AccountOwnership.OWNER
                    elif role == "Procuration":
                        return AccountOwnership.ATTORNEY


class InvestTokenPage(LoggedPage, JsonPage):
    def get_invest_token(self):
        return Dict("token")(self.doc)


class LifeInsurancePage(LoggedPage, JsonPage):
    @method
    class fill_account(ItemElement):
        obj_id = Dict("id")
        obj_opening_date = Date(CleanText(Dict("subscriptionDate")))

        # No mention of currency in API
        obj_currency = "EUR"

    @method
    class iter_investments(DictElement):
        def find_elements(self):
            # Each investment is in a child node of contractInvestment with a specific name.
            for el in Dict("contractInvestment")(self):
                yield Dict("contractInvestment")(self).get(el)

        class item(ItemElement):
            klass = Investment

            obj_code = IsinCode(CleanText(Dict("isin")), default=NotAvailable)
            obj_code_type = IsinType(CleanText(Dict("isin")), default=NotAvailable)
            obj_label = Dict("name")
            obj_unitvalue = CleanDecimal.SI(Dict("partValue"), default=NotAvailable)
            obj_quantity = CleanDecimal.SI(Dict("partNumber"), default=NotAvailable)
            obj_valuation = CleanDecimal.SI(Dict("amount"))
            obj_vdate = Date(CleanText(Dict("dateValue")), default=NotAvailable)

            def obj_diff_ratio(self):
                diff_ratio_percent = CleanDecimal.SI(Dict("gainOrLoss"), default=None)(self)
                if diff_ratio_percent:
                    return diff_ratio_percent / 100
                return NotAvailable

            def obj_portfolio_share(self):
                portfolio_share_percent = CleanDecimal.SI(Dict("allocationPercentage"), default=None)(self)
                if portfolio_share_percent:
                    return portfolio_share_percent / 100
                return NotAvailable


class HistoryPage(LoggedPage, JsonPage):
    def is_empty_page(self):
        return len(self.doc) == 0

    @method
    class iter_history(DictElement):
        class item(ItemElement):
            klass = Transaction

            # Not sure that Dict('id') is unique and persist
            # wait for the full API migration
            obj__web_id = Eval(str, Dict("id"))
            obj_amount = CleanDecimal(Dict("amount"))
            obj_date = Date(Dict("effectiveDate"))
            obj_type = Map(Upper(Dict("type")), Transaction.TYPES, Transaction.TYPE_UNKNOWN)

            def obj_raw(self):
                return Transaction.Raw(Lower(Dict("detail")))(self) or Format("%s %s", Field("date"), Field("amount"))(
                    self
                )


class ComingPage(LoggedPage, JsonPage):
    @method
    class iter_coming(DictElement):
        item_xpath = "futureOperations"

        class item(ItemElement):
            klass = Transaction

            obj_amount = CleanDecimal(Dict("amount"))
            obj_date = Date(Dict("effectiveDate"))
            obj_vdate = Date(Dict("operationDate"))
            obj_type = Map(Upper(Dict("type")), Transaction.TYPES, Transaction.TYPE_UNKNOWN)

            def obj_raw(self):
                return Transaction.Raw(Lower(Dict("label")))(self) or Format("%s %s", Field("date"), Field("amount"))(
                    self
                )

    @method
    class fill_account_coming(ItemElement):
        klass = Account

        obj_coming = CleanDecimal(Dict("totalAmount", default=NotAvailable), default=NotAvailable)


class AccountInfoPage(LoggedPage, JsonPage):
    def get_iban(self):
        return self.doc["iban"].replace(" ", "")


class RedirectOldPage(LoggedPage, HTMLPage):
    # We land here when going away from bourse website.
    # bourse.ing.fr -> secure.ing.fr (here) -> to whatever the form points
    def on_load(self):
        self.get_form(name="module").submit()


class BourseLandingPage(HTMLPage):
    # when going to bourse space, we land on this page, which is logged
    # that's all what this class is for: know we're logged
    @property
    def logged(self):
        return "Réessayez après vous être de nouveau authentifié" not in CleanText(
            '//div[@class="error-pages-message"]'
        )(self.doc)


class RedirectBourseToApi(LoggedPage, HTMLPage):
    def submit_form(self):
        form = self.get_form()
        form.submit()
