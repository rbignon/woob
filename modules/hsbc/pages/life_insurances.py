# coding: utf-8
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

# flake8: compatible

from __future__ import unicode_literals

import re
from decimal import Decimal

from woob.capabilities import NotAvailable
from woob.capabilities.bank import AccountNotFound
from woob.capabilities.bank.wealth import Investment
from woob.tools.capabilities.bank.transactions import FrenchTransaction
from woob.browser.elements import TableElement, ItemElement, method
from woob.browser.pages import HTMLPage, LoggedPage, FormNotFound
from woob.browser.filters.standard import (
    CleanText, CleanDecimal, Field, Regexp, Eval, Date, Lower,
)
from woob.browser.filters.html import Link, XPathNotFound, TableCell
from woob.browser.filters.javascript import JSVar

from .account_pages import Transaction

""" Life insurance subsite related pages """


class LITransaction(FrenchTransaction):
    PATTERNS = [
        (re.compile(r'^(?P<text>Arbitrage.*)'), FrenchTransaction.TYPE_ORDER),
        (re.compile(r'^(?P<text>Versement.*)'), FrenchTransaction.TYPE_DEPOSIT),
        (re.compile(r'^(?P<text>.*)'), FrenchTransaction.TYPE_BANK),
    ]


class LifeInsurancePortal(LoggedPage, HTMLPage):
    def is_here(self):
        try:
            self.get_form(name='FORM_ERISA')
        except FormNotFound:
            return False
        return True

    def on_load(self):
        self.logger.debug('automatically following form')
        form = self.get_form(name='FORM_ERISA')
        form['token'] = JSVar(CleanText('//script'), var='document.FORM_ERISA.token.value')(self.doc)
        form.submit()


class LifeInsuranceFingerprintForm(LoggedPage, HTMLPage):
    """
    For some accounts, when we try to go to a lifeinsurance account page,
    we are redirected to an empty page with an automatic form.
    It looks like to be a kind of recaptcha that fingerprint use js to
    fingerprint the browser and send the resulting string back inside the
    DevicePrint attribute.
    If you submit this form with the empty field or the "No Data" value,
    you are simply redirected to the frame_page.
    For the moment we do nothing, but maybe we could access these few
    limited accounts by properly filling the fingerprint and submitting
    """
    is_here = '//form[@name="formSaisie"]/input[@id="DevicePrint"]'


class LifeInsuranceMain(LoggedPage, HTMLPage):
    def on_load(self):
        self.logger.debug('automatically following form')
        form = self.get_form(name='formAccueil')
        form.url = 'https://assurances.hsbc.fr/navigation'
        form.submit()


class LifeInsurancesPage(LoggedPage, HTMLPage):
    @method
    class iter_history(TableElement):
        head_xpath = '(//table)[1]/thead/tr/th'
        item_xpath = '(//table)[1]/tbody/tr'

        col_label = "Actes"
        col_date = "Date d'effet"
        col_amount = "Montant net"
        col_gross_amount = "Montant brut"

        class item(ItemElement):
            klass = LITransaction

            obj_raw = LITransaction.Raw(CleanText(TableCell('label')))
            obj_date = Date(CleanText(TableCell('date')))
            obj_amount = Transaction.Amount(TableCell('amount'), TableCell('gross_amount'), replace_dots=False)

    @method
    class iter_investments(TableElement):
        head_xpath = '//div[contains(., "Détail de vos supports")]/following-sibling::div/table/thead/tr/th'
        item_xpath = '//div[contains(., "Détail de vos supports")]/following-sibling::div/table/tbody/tr[not(contains(@class, "light-yellow"))]'

        col_label = "Support"
        col_vdate = "Date de valorisation *"
        col_quantity = ["Nombre d'unités de compte", re.compile("Nombre de parts")]
        col_portfolio_share = "Répartition"
        col_unitvalue = ["Valeur liquidative", re.compile("Valeur de la part")]
        col_support_value = re.compile("Valeur support")
        col_diff_ratio = "Plus/Moins"

        class item(ItemElement):
            klass = Investment

            obj_label = CleanText(TableCell('label'))
            obj_vdate = Date(CleanText(TableCell('vdate')), dayfirst=True)
            obj_portfolio_share = Eval(lambda x: x / 100, CleanDecimal.SI(TableCell('portfolio_share')))
            obj_unitvalue = CleanDecimal.SI(TableCell('unitvalue'), default=NotAvailable)
            obj_quantity = CleanDecimal.SI(TableCell('quantity'), default=NotAvailable)
            obj_valuation = CleanDecimal.SI(TableCell('support_value'))
            # The currency is not displayed on each invest line but the headers in the table indicate that the values are in EUR
            obj_original_currency = 'EUR'

            def obj_diff_ratio(self):
                diff_ratio_el = self.el.xpath('.//td')[4]
                val = diff_ratio_el.text_content().strip().strip('%')
                if val == '-':
                    return NotAvailable
                try:
                    img = diff_ratio_el.xpath('.//img')[0]
                    is_negative = 'decrease' in img.attrib['src']
                except Exception:
                    self.logger.debug("didn't find decrease img")
                    is_negative = False
                val = Decimal(val)
                if val > Decimal('0') and is_negative:
                    val *= -1
                return val / 100

            def obj_code(self):
                euro_funds_label = ['support euros', 'fonds en euros']
                if any(eur_label in Lower(Field('label'))(self) for eur_label in euro_funds_label):
                    return NotAvailable
                return Regexp(
                    Link('.//a', default=None),
                    r'javascript:openSupportPerformanceWindow\(\'(.*?)\', \'(.*?)\'\)',
                    r'\2',
                    default=NotAvailable
                )(self)

            def condition(self):
                return len(self.el.xpath('.//td')) > 1

    def get_lf_attributes(self, lfid):
        attributes = {}

        # values can be in JS var format but it's not mandatory param so we don't go to get the real value
        try:
            values = Regexp(
                Link('//a[contains(., "%s")]' % lfid[:-3].lstrip('0')), r'\((.*?)\)'
            )(self.doc)
            values = values.replace(' ', '').replace("'", '').split(',')
        except XPathNotFound:
            raise AccountNotFound('cannot find account id %s on life insurance site' % lfid)
        keys = Regexp(CleanText('//script'), r'consultationContrat\((.*?)\)')(self.doc).replace(' ', '').split(',')

        attributes = dict(zip(keys, values))
        return attributes

    def disconnect(self):
        self.get_form(name='formDeconnexion').submit()


class LifeInsuranceUseless(LoggedPage, HTMLPage):
    is_here = '//h1[text()="Assurance Vie"]'


class LifeNotFound(LoggedPage, HTMLPage):
    pass
