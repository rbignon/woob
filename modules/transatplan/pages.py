# -*- coding: utf-8 -*-

# Copyright(C) 2012-2021  Budget Insight
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

from __future__ import unicode_literals

from weboob.capabilities.bank import Account, Investment, Transaction
from weboob.browser.pages import HTMLPage, LoggedPage
from weboob.browser.elements import TableElement, ItemElement, method
from weboob.browser.filters.standard import (
    CleanText, Regexp, CleanDecimal, Format, Currency, Date,
)
from weboob.browser.filters.html import TableCell
from weboob.tools.compat import urljoin


class LoginPage(HTMLPage):
    def login(self, username, password):
        form = self.get_form(name='ident')
        form['_cm_user'] = username
        form['_cm_pwd'] = password
        form.submit()

    def get_error(self):
        return CleanText('//div[has-class("alerte")]')(self.doc)


class MultiPage(LoggedPage, HTMLPage):
    def iter_contracts(self):
        for a in self.doc.xpath('//div[has-class("consulter")]//li/a'):
            yield urljoin(self.url, a.attrib['href']), a.text_content()

    def go_accounts(self):
        form = self.get_form(id='P:F', submit='.//input[@value="Vos comptes"]')
        form.submit()

    @method
    class iter_especes(TableElement):
        head_xpath = '//table[@summary="Relevé de vos comptes espèces"]/thead/tr/th'
        item_xpath = '//table[@summary="Relevé de vos comptes espèces"]/tbody/tr'

        col_balance = 'Solde'
        col_label = 'Compte'

        class item(ItemElement):
            klass = Account

            obj_type = Account.TYPE_MARKET
            obj_balance = CleanDecimal(TableCell('balance'), replace_dots=True)
            obj_currency = Currency(TableCell('balance'))
            obj_label = CleanText(TableCell('label'))
            obj_id = Regexp(obj_label, r'^(\d+)')

            def obj_url(self):
                for a in TableCell('label')(self)[0].xpath('./a'):
                    return a.attrib['href']

    class titres(TableElement):
        head_xpath = '//table[@summary="Relevé de vos comptes titres"]/thead/tr/th'
        item_xpath = '//table[@summary="Relevé de vos comptes titres"]/tbody/tr'

        col_cat = 'Catégorie'
        col_label = 'Valeur'
        col_quantity = 'Quantité'
        col_diff = "Plus-value d'acquisition / Gain d'acquisition"
        col_valuation = 'Valorisation 1'

    @method
    class iter_titres(titres):
        class item(ItemElement):
            klass = Account

            def condition(self):
                return not CleanText('.')(self).startswith('Total')

            obj_type = Account.TYPE_MARKET
            obj_balance = CleanDecimal(TableCell('valuation'), replace_dots=True)
            obj_currency = Currency(TableCell('valuation'))
            obj_label = Format('%s %s', CleanText(TableCell('cat')), CleanText(TableCell('label')))
            obj_valuation_diff = CleanDecimal(TableCell('diff'), replace_dots=True)
            obj_id = Regexp(CleanText(TableCell('label')), r'\((\w+)\)')

    @method
    class iter_investment(titres):
        class item(ItemElement):
            klass = Investment

            def condition(self):
                return not CleanText('.')(self).startswith('Total')

            obj_quantity = CleanDecimal(TableCell('quantity'), replace_dots=True)
            obj_valuation = CleanDecimal(TableCell('valuation'), replace_dots=True)
            obj_label = CleanText(TableCell('label'))
            obj_code = Regexp(CleanText(TableCell('label')), r'\((\w+)\)')
            obj_code_type = Investment.CODE_TYPE_ISIN
            obj_portfolio_share = 1
            obj_diff = CleanDecimal(TableCell('diff'), replace_dots=True)


class HistoryPage(LoggedPage, HTMLPage):
    is_here = '//p[@class="a_titre2"][starts-with(normalize-space(text()),"Dernières opérations")]'

    @method
    class iter_history(TableElement):
        head_xpath = '//table[@summary="Liste des mouvements du compte espèces"]/thead/tr/th'
        item_xpath = '//table[@summary="Liste des mouvements du compte espèces"]/tbody/tr'

        col_date = 'Date opération'
        col_vdate = 'Date valeur'
        col_label = 'Libellé opération'
        col_debit = 'Débit'
        col_credit = 'Crédit'

        class item(ItemElement):
            klass = Transaction

            obj_raw = CleanText(TableCell('label'))
            obj_date = Date(CleanText(TableCell('date')), dayfirst=True)
            obj_vdate = Date(CleanText(TableCell('vdate')), dayfirst=True)

            def obj_amount(self):
                debit = CleanDecimal(TableCell('debit'), replace_dots=True, default=0)(self)
                credit = CleanDecimal(TableCell('credit'), replace_dots=True, default=0)(self)
                assert not (debit and credit)
                return credit - debit

