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

# flake8: compatible

from __future__ import unicode_literals

import re
from decimal import Decimal

from woob.capabilities.base import NotAvailable, empty
from woob.capabilities.bank import Account, Transaction
from woob.capabilities.wealth import Investment, Pocket
from woob.browser.pages import HTMLPage, LoggedPage, FormNotFound
from woob.browser.elements import TableElement, ItemElement, method
from woob.browser.filters.standard import (
    CleanText, Regexp, CleanDecimal, Format, Currency, Date, Field,
    Env, Lower,
)
from woob.browser.filters.html import TableCell, Link, Attr, AbsoluteLink
from woob.exceptions import BrowserUnavailable, ActionNeeded
from woob.tools.capabilities.bank.investments import IsinCode, IsinType


def percent_to_ratio(value):
    if empty(value):
        return NotAvailable
    return value / 100


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


class SituationPage(LoggedPage, HTMLPage):
    def get_action_needed(self):
        # Following span tags contain instructions, we only fetch the first one
        return CleanText('//div[@class="bloctxt"]/span[1]')(self.doc)


class HomePage(LoggedPage, HTMLPage):
    def on_load(self):
        cgu_message = CleanText('//p[@id="F:expP"]', default=None)(self.doc)
        if 'Conditions Générales' in cgu_message:
            raise ActionNeeded(cgu_message)
        self.browser.account.go()


class AccountPage(LoggedPage, MyHTMLPage):
    def is_here(self):
        return self.doc.xpath('//p[contains(text(), "Relevé de vos comptes")]')

    def on_load(self):
        if CleanText('//input[contains(@src, "retour")]/@src')(self.doc):
            self.do_return()

    def has_no_account(self):
        return bool(
            CleanText('//p[contains(text(), "aucun compte espèce")]')(self.doc)
            and CleanText('//p[contains(text(), "aucun titre")]')(self.doc)
        )

    def get_company_name(self):
        return CleanText('(//li[contains(@class, "contract_only")]/a)[1]', default=NotAvailable)(self.doc)

    @method
    class iter_especes(TableElement):
        head_xpath = '//table[@summary="Relevé de vos comptes espèces"]/thead/tr/th'
        item_xpath = '//table[@summary="Relevé de vos comptes espèces"]/tbody/tr'

        col_balance = 'Solde'
        col_label = 'Compte'

        class item(ItemElement):
            klass = Account

            obj_type = Account.TYPE_CHECKING
            obj_balance = CleanDecimal.French(TableCell('balance'))
            obj_currency = Currency(TableCell('balance'))
            obj_label = CleanText(TableCell('label'))
            obj_id = Regexp(obj_label, r'^(\d+)')
            obj_number = obj_id

            def obj_url(self):
                return Link(TableCell('label')(self)[0].xpath('./a'))(self)

    @method
    class iter_titres(TableElement):
        head_xpath = '//table[@summary="Relevé de vos comptes titres"]/thead/tr/th'
        item_xpath = '//table[@summary="Relevé de vos comptes titres"]/tbody/tr'

        def condition(self):
            return not CleanText(
                '//table[@summary="Relevé de vos comptes titres"]//p[contains(text(), "aucun titre")]'
            )(self)

        col_cat = 'Catégorie'
        col_label = 'Valeur'
        col_quantity = 'Quantité'
        col_diff = "Plus-value d'acquisition / Gain d'acquisition"
        col_valuation = re.compile(r'Valorisation \d')

        class item(ItemElement):
            klass = Account

            def condition(self):
                return not CleanText('.')(self).startswith('Total')

            obj_id = Attr('./following-sibling::tr/td[1]/span', 'title') & CleanText
            obj_type = Account.TYPE_MARKET
            obj_balance = CleanDecimal.French(TableCell('valuation'))
            obj_currency = Currency(TableCell('valuation'))
            obj_label = Format('%s %s', CleanText(TableCell('cat')), CleanText(TableCell('label')))
            obj_valuation_diff = CleanDecimal.French(TableCell('diff'), default=NotAvailable)
            obj_number = obj_id
            obj_label = Format('%s %s', CleanText(TableCell('cat')), CleanText(TableCell('label')))

    @method
    class iter_investment(TableElement):
        head_xpath = '//table[@summary="Relevé de vos comptes titres"]/thead/tr/th'
        item_xpath = '//table[@summary="Relevé de vos comptes titres"]/tbody/tr'

        col_cat = 'Catégorie'
        col_label = 'Valeur'
        col_quantity = 'Quantité'
        col_diff = "Plus-value d'acquisition / Gain d'acquisition"
        col_valuation = re.compile(r'Valorisation \d')

        class item(ItemElement):
            klass = Investment

            def condition(self):
                return not CleanText('.//span[contains(text(), "Total compte titre")]')(self)

            obj_quantity = CleanDecimal.French(TableCell('quantity'))
            obj_valuation = CleanDecimal.French(TableCell('valuation'))
            obj_portfolio_share = Decimal(1)
            obj_diff = CleanDecimal.French(TableCell('diff'), default=NotAvailable)
            obj_label = CleanText(TableCell('label'))

            def obj__performance_url(self):
                return Link(TableCell('label')(self)[0].xpath('./a'))(self)

            obj_code = IsinCode(Regexp(CleanText(TableCell('label')), r'\((.*?)\)'), default=NotAvailable)
            obj_code_type = IsinType(Field('code'), default=NotAvailable)


class InvestmentDetailPage(LoggedPage, MyHTMLPage):
    def is_here(self):
        return self.doc.xpath('//a[contains(text(), "cotation de la valeur")]')

    def get_performance_link(self):
        return Link('//a[@id="L"]', default=None)(self.doc)

    @method
    class fill_investment(ItemElement):
        obj_unitvalue = CleanDecimal.French(
            '//table[@summary="Historique des cours de la valeur"]//tr[1]//td[5]',
            default=NotAvailable
        )
        obj_vdate = Date(
            CleanText(
                '//table[@summary="Historique des cours de la valeur"]//tr[1]//td[1]'
            ),
            dayfirst=True,
            default=NotAvailable
        )


class InvestmentPerformancePage(LoggedPage, MyHTMLPage):
    @method
    class fill_investment(ItemElement):
        obj_asset_category = CleanText('//th[text()="Type de valeur"]/following-sibling::td[1]')

        def obj_performance_history(self):
            # Only available performance is "52 weeks" (1 year)
            return {
                1: percent_to_ratio(CleanDecimal.French('//th[text()="52 semaines"]/following-sibling::td[1]')(self)),
            }


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


class PocketsPage(LoggedPage, MyHTMLPage):
    @method
    class iter_pocket(TableElement):
        head_xpath = '//table[@summary="Relevé de vos attributions d\'actions"]/thead/tr/th'
        item_xpath = '//table[@summary="Relevé de vos attributions d\'actions"]/tbody/tr'

        col_label = 'Attribution'
        col_condition = 'Conditions de performance'
        col_date = "Date d'acquisition définitive des droits"
        col_locked_quantity = 'Actions à livrer'
        col_unlocked_quantity = re.compile(r'Actions livrées')
        col_valuation = re.compile(r'Valorisation \d')

        class item(ItemElement):
            klass = Pocket

            # pockets with positive quantity are the ones that are still "locked",
            # it means the availability_date has not been reached yet.
            # those pockets are the ones we are missing as we already fetched the "unlocked" ones.
            def condition(self):
                return Field('quantity')(self) > 0

            def obj_label(self):
                inv = Env('inv')(self)
                return inv.label

            def obj_quantity(self):
                unlocked_qty = CleanDecimal.French(TableCell('unlocked_quantity'), default=0)(self)
                locked_qty = CleanDecimal.French(TableCell('locked_quantity'), default=0)(self)
                return unlocked_qty + locked_qty

            def obj_amount(self):
                inv = Env('inv')(self)
                amount = CleanDecimal.French(TableCell('valuation'), default=NotAvailable)(self)
                if not amount and inv.unitvalue:
                    amount = Field('quantity')(self) * Decimal(inv.unitvalue)
                return amount

            obj_availability_date = Date(CleanText(TableCell('date')), dayfirst=True, default=NotAvailable)
            obj_investment = Env('inv')

            def obj_condition(self):
                locked_qty = CleanDecimal.French(TableCell('locked_quantity'), default=0)(self)
                if Field('availability_date')(self) and locked_qty:
                    return Pocket.CONDITION_DATE
                return Pocket.CONDITION_AVAILABLE

            def obj__details_url(self):
                return AbsoluteLink('.//a', default=NotAvailable)(self)


class PocketDetailPage(LoggedPage, MyHTMLPage):
    def get_underlying_invest(self):
        return Lower('//a[@id="L5"]/text()')(self.doc)


class ErrorPage(HTMLPage):
    def is_here(self):
        return self.doc.xpath('//div[@class="blocmsg err" and contains(text(), "Problème technique")]')

    def on_load(self):
        raise BrowserUnavailable(CleanText('//main/div[has-class("err")]')(self.doc))
