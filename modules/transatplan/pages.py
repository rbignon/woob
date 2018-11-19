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

from weboob.capabilities.bank import Account, Investment, Transaction, Pocket
from weboob.browser.pages import HTMLPage, LoggedPage, FormNotFound
from weboob.browser.elements import TableElement, ItemElement, method
from weboob.browser.filters.standard import (
    CleanText, Regexp, CleanDecimal, Format, Currency, Date,
)
from weboob.browser.filters.html import TableCell, Link
from weboob.exceptions import BrowserUnavailable


class MyHTMLPage(HTMLPage):
    # may need to submit the return form
    # otherwise, the page blocks everything
    def do_return(self):
        try:
            form = self.get_form(id='SubmitRet')
            if '_FID_DoDeviseChange' in form:
                form.pop('_FID_DoDeviseChange')
            if '_FID_DoActualiser' in form:
                form.pop('_FID_DoActualiser')
            form.submit()
        except FormNotFound:
            return


class LoginPage(HTMLPage):
    def login(self, username, password):
        form = self.get_form(name='bloc_ident')
        form['_cm_user'] = username
        form['_cm_pwd'] = password
        form.submit()

    def get_error(self):
        return CleanText('//div[has-class("alerte")]')(self.doc)


class HomePage(LoggedPage, HTMLPage):
    def on_load(self):
        self.browser.account.go()


class AccountPage(LoggedPage, MyHTMLPage):
    def is_here(self):
        return self.doc.xpath('//p[contains(text(), "Relevé de vos comptes")]')

    def on_load(self):
        if CleanText('//input[contains(@src, "retour")]/@src')(self.doc):
            self.do_return()

    @method
    class iter_especes(TableElement):
        head_xpath = '//table[@summary="Relevé de vos comptes espèces"]/thead/tr/th'
        item_xpath = '//table[@summary="Relevé de vos comptes espèces"]/tbody/tr'

        col_balance = 'Solde'
        col_label = 'Compte'

        class item(ItemElement):
            klass = Account

            obj_type = Account.TYPE_CHECKING
            obj_balance = CleanDecimal(TableCell('balance'), replace_dots=True)
            obj_currency = Currency(TableCell('balance'))
            obj_label = CleanText(TableCell('label'))
            obj_id = Regexp(obj_label, r'^(\d+)')

            def obj_url(self):
                return Link(TableCell('label')(self)[0].xpath('./a'))(self)

    @method
    class iter_titres(TableElement):
        head_xpath = '//table[@summary="Relevé de vos comptes titres"]/thead/tr/th'
        item_xpath = '//table[@summary="Relevé de vos comptes titres"]/tbody/tr'

        def condition(self):
            return not CleanText('//table[@summary="Relevé de vos comptes titres"]//p[contains(text(), "aucun titre")]')(self)

        col_cat = 'Catégorie'
        col_label = 'Valeur'
        col_quantity = 'Quantité'
        col_diff = "Plus-value d'acquisition / Gain d'acquisition"
        col_valuation = 'Valorisation 1'

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
            obj_label = Format('%s %s', CleanText(TableCell('cat')), CleanText(TableCell('label')))

            def obj__url_pocket(self):
                return Link(TableCell('cat')(self)[0].xpath('./a'))(self)

            def obj__url_invest(self):
                return Link(TableCell('label')(self)[0].xpath('./a'))(self)

    @method
    class iter_investment(TableElement):
        head_xpath = '//table[@summary="Relevé de vos comptes titres"]/thead/tr/th'
        item_xpath = '//table[@summary="Relevé de vos comptes titres"]/tbody/tr'

        col_cat = 'Catégorie'
        col_label = 'Valeur'
        col_quantity = 'Quantité'
        col_diff = "Plus-value d'acquisition / Gain d'acquisition"
        col_valuation = 'Valorisation 1'

        class item(ItemElement):
            klass = Investment

            def condition(self):
                return not CleanText('.//span[contains(text(), "Total compte titre")]')(self)

            obj_quantity = CleanDecimal(TableCell('quantity'), replace_dots=True)
            obj_valuation = CleanDecimal(TableCell('valuation'), replace_dots=True)
            obj_portfolio_share = 1
            obj_diff = CleanDecimal(TableCell('diff'), replace_dots=True)
            obj_label = CleanText(TableCell('label'))
            obj_code_type = Investment.CODE_TYPE_ISIN
            obj_code = Regexp(CleanText(TableCell('label')), '\((.*?)\)')


class HistoryPage(LoggedPage, MyHTMLPage):
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

        def condition(self):
            return not CleanText('//p[contains(text(), "Vous n\'avez aucun mouvement enregistré")]')(self)

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


class PocketPage(LoggedPage, MyHTMLPage):
    @method
    class iter_pocket(TableElement):
        head_xpath = '//table[@summary="Liste des opérations par émission"]/thead/tr/th'
        item_xpath = '//table[@summary="Liste des opérations par émission"]/tbody/tr'

        col_date = ('Date de la levée', 'Date de livraison')
        col_quantity = 'Quantité de titres'
        col_valuation = 'Valorisation 1'

        class item(ItemElement):
            klass = Pocket

            obj_quantity = CleanDecimal(TableCell('quantity'), replace_dots=True)
            obj_amount = CleanDecimal(TableCell('valuation'), replace_dots=True)
            obj_availability_date = Date(CleanText(TableCell('date')))
            obj__invest_name = CleanText('//th[text()="Valeur"]/following-sibling::td')
            obj_label = Format('%s %s',
                               CleanText('//th[text()="Valeur"]/following-sibling::td'),
                               Date(CleanText(TableCell('date'))))


class ErrorPage(HTMLPage):
    def is_here(self):
        return self.doc.xpath('//div[@class="blocmsg err" and contains(text(), "Problème technique")]')

    def on_load(self):
        raise BrowserUnavailable(CleanText('//main/div[has-class("err")]')(self.doc))
