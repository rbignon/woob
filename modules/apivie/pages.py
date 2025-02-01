# Copyright(C) 2013      Romain Bignon
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

from woob.browser.elements import DictElement, ItemElement, method
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import CleanDecimal, CleanText, Date, Eval, Field, Lower, MapIn
from woob.browser.pages import HTMLPage, JsonPage, LoggedPage, RawPage, XMLPage
from woob.capabilities.bank import Account
from woob.capabilities.bank.wealth import Investment
from woob.capabilities.base import NotAvailable, empty
from woob.tools.capabilities.bank.investments import IsinCode, IsinType
from woob.tools.capabilities.bank.transactions import FrenchTransaction


class LoginPage(RawPage):
    def build_doc(self, content):
        if re.compile(r"^<.*>.*</.*>$").match(content.decode()):
            return XMLPage.build_doc(self, self.response.content)
        return JsonPage.build_doc(self, content)

    def get_access_token(self):
        if isinstance(self.doc, dict):
            return Dict("accessToken")(self.doc)
        return CleanText("//accessToken")(self.doc)

    def get_error_message(self):
        if isinstance(self.doc, dict):
            return Dict("message")(self.doc)
        return CleanText("//message")(self.doc)


class InfoPage(LoggedPage, HTMLPage):
    pass


class HomePage(LoggedPage, HTMLPage):
    pass


ACCOUNT_TYPES = {
    "apivie": Account.TYPE_LIFE_INSURANCE,
    "liberalys vie": Account.TYPE_LIFE_INSURANCE,
    "linxea zen": Account.TYPE_LIFE_INSURANCE,
    "frontière efficiente": Account.TYPE_LIFE_INSURANCE,
    "cristalliance vie": Account.TYPE_LIFE_INSURANCE,
    "article 82": Account.TYPE_LIFE_INSURANCE,
    "intencial horizon": Account.TYPE_LIFE_INSURANCE,
    "intencial archipel": Account.TYPE_LIFE_INSURANCE,
    "liberalys retraite": Account.TYPE_PER,
    "perspective génération": Account.TYPE_PER,
    "perp": Account.TYPE_PERP,
    "capi": Account.TYPE_CAPITALISATION,
}


class AccountsPage(LoggedPage, JsonPage):
    @method
    class iter_accounts(DictElement):

        class item(ItemElement):
            klass = Account

            obj_id = obj_number = CleanText(Dict("contratId"))
            obj_label = CleanText(Dict("produit"))
            obj_balance = CleanDecimal.SI(Dict("encours"))
            obj_currency = "EUR"
            obj_type = MapIn(Lower(Field("label")), ACCOUNT_TYPES, Account.TYPE_UNKNOWN)


class InvestmentPage(LoggedPage, JsonPage):
    @method
    class iter_investments(DictElement):
        item_xpath = "portefeuille"

        class item(ItemElement):
            klass = Investment

            obj_label = CleanText(Dict("libelle"))
            obj_valuation = CleanDecimal.SI(Dict("valorisation"))
            obj_code = IsinCode(CleanText(Dict("code")), default=NotAvailable)
            obj_code_type = IsinType(CleanText(Dict("code")), default=NotAvailable)
            obj_quantity = CleanDecimal.SI(Dict("nombreDeParts", default=None), default=NotAvailable)
            obj_unitvalue = CleanDecimal.SI(Dict("valeurActuelle", default=None), default=NotAvailable)
            obj_unitprice = CleanDecimal.SI(Dict("valeurAchat", default=None), default=NotAvailable)

            def obj_portfolio_share(self):
                share = CleanDecimal.SI(Dict("repartition"), default=NotAvailable)(self)
                if empty(share):
                    return NotAvailable
                return Eval(lambda x: x / 100, share)(self)

            def obj_diff_ratio(self):
                diff_ratio = CleanDecimal.SI(Dict("performance", default=None), default=NotAvailable)(self)
                if empty(diff_ratio):
                    return NotAvailable
                return Eval(lambda x: x / 100, diff_ratio)(self)

            def obj_srri(self):
                srri = CleanDecimal.SI(Dict("risque"), default=NotAvailable)(self)
                if empty(srri) or srri == 0:
                    return NotAvailable
                return int(srri)

    def get_opening_date(self):
        return Date(CleanText(Dict("dateEffet")), default=NotAvailable)(self.doc)


class Transaction(FrenchTransaction):
    pass


class HistoryPage(LoggedPage, JsonPage):
    @method
    class iter_history(DictElement):
        # No item_xpath needed

        class item(ItemElement):
            klass = Transaction

            obj_label = CleanText(Dict("typeMouvement"))
            obj_amount = CleanDecimal.SI(Dict("montantOperation"))
            obj_date = obj_rdate = Date(CleanText(Dict("dateOperation")))
            obj_type = Transaction.TYPE_BANK

            class obj_investments(DictElement):
                item_xpath = "sousOperations"

                def condition(self):
                    return Dict("sousOperations", default=None)(self)

                class item(ItemElement):
                    klass = Investment

                    obj_label = CleanText(Dict("typeMouvement"))
                    obj_valuation = CleanDecimal.SI(Dict("montantOperation"))
                    obj_vdate = Date(CleanText(Dict("dateOperation")))

            def validate(self, obj):
                # Skip 'Encours' transactions, it is just an information
                # about the current account balance
                return "Encours" not in obj.label
