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
from woob.capabilities.bank.wealth import Investment, Pocket
from woob.browser.pages import HTMLPage, LoggedPage, FormNotFound
from woob.browser.elements import TableElement, ItemElement, method
from woob.browser.filters.standard import (
    CleanText, Regexp, CleanDecimal, Format, Currency, Date, Field,
    Env,
)
from woob.browser.filters.html import TableCell, Link, Attr
from woob.exceptions import BrowserUnavailable, ActionNeeded
from woob.tools.capabilities.bank.investments import IsinCode, IsinType
from woob.tools.date import date


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


class ActionNeededPage(LoggedPage, HTMLPage):
    is_here = '//form//table//label[@for="acrgpd:DataEntry"]'

    def get_action_needed(self):
        # User has to accept GDPR rules after logging in
        return CleanText(
            '//p[contains(text(), "RGPD – Règlement général sur la protection des données personnelles")]'
        )(self.doc)


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

    def has_no_market_account(self):
        return CleanText(
            '//table[@summary="Relevé de vos comptes titres"]//p[contains(text(), "aucun titre")]'
        )(self.doc)

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

    def get_invest_label(self):
        return CleanText('//p[contains(@id, "VAL_Entete")]/text()')(self.doc)


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
    def is_here(self):
        return self.doc.xpath('//p[contains(text(), "Votre situation")]')

    def get_detail_url(self, pocket_id):
        return Link('//a[contains(@href, "%s")]' % pocket_id)(self.doc)

    def has_pockets(self):
        return bool(self.doc.xpath('//table[@summary="Relevé de vos attributions d\'actions"]/tbody/tr'))

    def get_pocket_details_link(self):
        return Link(
            '//table[@summary="Relevé de vos attributions d\'actions"]//td[1]//a',
            default=NotAvailable
        )(self.doc)

    def get_currency(self):
        return Currency('//td[contains(@class, "tittot")][2]')(self.doc)

    def get_valuation(self):
        return CleanDecimal.French(
            '//td[contains(@class, "tittot")][2]',
            default=NotAvailable
        )(self.doc)

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

            def obj_label(self):
                inv = Env('inv', default=NotAvailable)(self)
                if inv:
                    return inv.label
                return CleanText(TableCell('label'))(self)

            def obj_quantity(self):
                unlocked_qty = CleanDecimal.French(TableCell('unlocked_quantity'), default=0)(self)
                locked_qty = CleanDecimal.French(TableCell('locked_quantity'), default=0)(self)
                return unlocked_qty + locked_qty

            def obj_amount(self):
                inv = Env('inv', default=NotAvailable)(self)
                amount = CleanDecimal.French(TableCell('valuation'), default=NotAvailable)(self)
                if not amount and inv:
                    amount = Field('quantity')(self) * Decimal(inv.unitvalue)
                return amount

            obj_investment = Env('inv', default=NotAvailable)
            obj__url_id = Regexp(
                Link('.//a', default=NotAvailable),
                r'IDTATB=(\d+)&',
                default=None
            )

            def validate(self, obj):
                return obj.quantity and obj.amount


class PocketDetailPage(LoggedPage, MyHTMLPage):
    def is_here(self):
        return self.doc.xpath('//p[contains(text(),"Votre attribution")]')

    def get_invest_url(self):
        return Link('//a[@id="L5"]', default=NotAvailable)(self.doc)

    def get_invest_isin(self):
        return IsinCode(
            Regexp(
                Link('//a[@id="L5"]', default=NotAvailable),
                r'CODVAL=(.*)',
                default=''
            ),
            default=NotAvailable
        )(self.doc)

    def get_back_url(self):
        return Link('//a[@id="B"]', default=NotAvailable)(self.doc)

    @method
    class fill_pocket(ItemElement):

        obj__acquisition_date = Date(
            CleanText('//th[text()="Date d\'acquisition définitive des droits"]/following-sibling::td[1]'),
            dayfirst=True,
            default=NotAvailable
        )

        def obj_availability_date(self):
            availability_date = Date(
                CleanText('//th[text()="Fin de conservation des titres"]/following-sibling::td[1]'),
                dayfirst=True,
                default=NotAvailable
            )(self)

            # the previous date can be missing, "Pas d'obligation de conservation" message is displayed instead,
            # in this case, "acquisition_date" equals "availability date".
            if not availability_date:
                return Field('_acquisition_date')(self)
            return availability_date

        def obj_condition(self):
            acquisition_date = Field('_acquisition_date')(self)
            availability_date = Field('availability_date')(self)

            if availability_date:
                if date.today() >= availability_date:
                    return Pocket.CONDITION_AVAILABLE

                if date.today() >= acquisition_date:
                    return Pocket.CONDITION_DATE_WHEN_TRANSFERABLE

                return Pocket.CONDITION_DATE_WHEN_ACQUIRED
            return Pocket.CONDITION_UNKNOWN


class ErrorPage(HTMLPage):
    def is_here(self):
        return self.doc.xpath('//div[@class="blocmsg err" and contains(text(), "Problème technique")]')

    def on_load(self):
        raise BrowserUnavailable(CleanText('//main/div[has-class("err")]')(self.doc))
