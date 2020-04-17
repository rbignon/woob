# -*- coding: utf-8 -*-

# Copyright(C) 2013      Romain Bignon
#
# This file is part of a weboob module.
#
# This weboob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This weboob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this weboob module. If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

from weboob.capabilities.base import NotAvailable, empty
from weboob.capabilities.bank import Account
from weboob.capabilities.wealth import Investment
from weboob.tools.capabilities.bank.transactions import FrenchTransaction
from weboob.browser.elements import TableElement, ItemElement, DictElement, method
from weboob.browser.pages import LoggedPage, HTMLPage, JsonPage
from weboob.browser.filters.standard import (
    CleanText, CleanDecimal, Date, Currency,
    Field, MapIn, Eval, Lower,
)
from weboob.browser.filters.html import TableCell
from weboob.browser.filters.json import Dict
from weboob.tools.capabilities.bank.investments import IsinCode, IsinType


class LoginPage(HTMLPage):
    def login(self, username, password):
        form = self.get_form(nr=0)
        form['_58_login'] = username.encode('utf-8')
        form['_58_password'] = password.encode('utf-8')
        form.submit()


class WrongpassPage(HTMLPage):
    pass


class InfoPage(LoggedPage, HTMLPage):
    def get_error_message(self):
        return CleanText('//span[@class="ui-messages-fatal-detail"]')(self.doc)


ACCOUNT_TYPES = {
    'apivie': Account.TYPE_LIFE_INSURANCE,
    'liberalys vie': Account.TYPE_LIFE_INSURANCE,
    'linxea zen': Account.TYPE_LIFE_INSURANCE,
    'frontière efficiente': Account.TYPE_LIFE_INSURANCE,
    'cristalliance vie': Account.TYPE_LIFE_INSURANCE,
    'liberalys retraite': Account.TYPE_PER,
    'perp': Account.TYPE_PERP,
}


class AccountsPage(LoggedPage, HTMLPage):
    @method
    class iter_accounts(TableElement):
        item_xpath = '//table[@summary="informations contrat"]/tbody/tr'
        head_xpath = '//table[@summary="informations contrat"]/thead/tr/th'

        col_id = 'N° du contrat'
        col_label = 'Produit'
        col_balance = 'Valorisation'

        class item(ItemElement):
            klass = Account

            obj_id = obj_number = CleanText(TableCell('id'))
            obj_label = CleanText(TableCell('label'))
            obj_balance = CleanDecimal.French(TableCell('balance'))
            obj_currency = Currency(TableCell('balance'))
            obj_type = MapIn(Lower(Field('label')), ACCOUNT_TYPES, Account.TYPE_UNKNOWN)


class InvestmentPage(LoggedPage, JsonPage):
    @method
    class iter_investments(DictElement):
        item_xpath = 'portefeuille'

        class item(ItemElement):
            klass = Investment

            obj_label = CleanText(Dict('libelle'))
            obj_valuation = CleanDecimal.SI(Dict('valorisation'))
            obj_code = IsinCode(CleanText(Dict('code')), default=NotAvailable)
            obj_code_type = IsinType(CleanText(Dict('code')), default=NotAvailable)
            obj_quantity = CleanDecimal.SI(Dict('nombreDeParts', default=None), default=NotAvailable)
            obj_unitvalue = CleanDecimal.SI(Dict('valeurActuelle', default=None), default=NotAvailable)
            obj_unitprice = CleanDecimal.SI(Dict('valeurAchat', default=None), default=NotAvailable)

            def obj_portfolio_share(self):
                share = CleanDecimal.SI(Dict('repartition'), default=NotAvailable)(self)
                if empty(share):
                    return NotAvailable
                return Eval(lambda x: x/100, share)(self)

            def obj_diff_ratio(self):
                diff_ratio = CleanDecimal.SI(Dict('performance', default=None), default=NotAvailable)(self)
                if empty(diff_ratio):
                    return NotAvailable
                return Eval(lambda x: x/100, diff_ratio)(self)

            def obj_srri(self):
                srri = CleanDecimal.SI(Dict('risque'), default=NotAvailable)(self)
                if empty(srri) or srri == 0:
                    return NotAvailable
                return int(srri)


class Transaction(FrenchTransaction):
    pass


class HistoryPage(LoggedPage, JsonPage):
    @method
    class iter_history(DictElement):
        # No item_xpath needed

        class item(ItemElement):
            klass = Transaction

            obj_label = CleanText(Dict('typeMouvement'))
            obj_amount = CleanDecimal.SI(Dict('montantOperation'))
            obj_date = obj_rdate = Date(CleanText(Dict('dateOperation')))
            obj_type = Transaction.TYPE_BANK

            class obj_investments(DictElement):
                item_xpath = 'sousOperations'

                def condition(self):
                    return Dict('sousOperations', default=None)(self)

                class item(ItemElement):
                    klass = Investment

                    obj_label = CleanText(Dict('typeMouvement'))
                    obj_valuation = CleanDecimal.SI(Dict('montantOperation'))
                    obj_vdate = Date(CleanText(Dict('dateOperation')))
