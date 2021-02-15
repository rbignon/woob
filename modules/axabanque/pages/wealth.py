# -*- coding: utf-8 -*-

# Copyright(C) 2016      Edouard Lambert
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

import re
from decimal import Decimal

from weboob.browser.pages import HTMLPage, JsonPage, LoggedPage
from weboob.browser.elements import ListElement, ItemElement, TableElement, DictElement, method
from weboob.browser.filters.standard import (
    CleanDecimal, CleanText, Currency, Date,
    Eval, Field, Lower, MapIn, QueryValue, Regexp,
)
from weboob.browser.filters.json import Dict
from weboob.browser.filters.html import Attr, Link, TableCell
from weboob.capabilities.bank import Account, AccountOwnership
from weboob.capabilities.wealth import Investment
from weboob.capabilities.profile import Person
from weboob.capabilities.base import NotAvailable, NotLoaded, empty
from weboob.tools.capabilities.bank.investments import IsinCode, IsinType
from weboob.tools.capabilities.bank.transactions import FrenchTransaction


def float_to_decimal(f):
    if empty(f):
        return NotAvailable
    return Decimal(str(f))


class AccountsPage(LoggedPage, HTMLPage):
    @method
    class iter_accounts(ListElement):
        item_xpath = '//div[contains(@data-module-open-link--link, "/savings/")]'

        class item(ItemElement):
            klass = Account

            def condition(self):
                # Filter out closed accounts
                return CleanDecimal.French('.//p[has-class("amount-card")]', default=None)(self) is not None

            TYPES = {
                'assurance vie': Account.TYPE_LIFE_INSURANCE,
                'perp': Account.TYPE_PERP,
                'epargne retraite agipi pair': Account.TYPE_PERP,
                'epargne retraite agipi far': Account.TYPE_MADELIN,
                'epargne retraite ma retraite': Account.TYPE_PER,
                'novial avenir': Account.TYPE_MADELIN,
                'epargne retraite novial': Account.TYPE_LIFE_INSURANCE,
            }

            obj_id = Regexp(CleanText('.//span[has-class("small-title")]'), r'([\d/]+)')
            obj_number = obj_id
            obj_label = CleanText('.//h3[has-class("card-title")]')
            obj_balance = CleanDecimal.French('.//p[has-class("amount-card")]', default=None)
            obj_valuation_diff = CleanDecimal.French('.//p[@class="performance"]', default=NotAvailable)
            obj_currency = Currency('.//p[has-class("amount-card")]')
            obj__acctype = "investment"
            obj_type = MapIn(Lower(Field('label')), TYPES, Account.TYPE_UNKNOWN)
            obj_url = Attr('.', 'data-module-open-link--link')
            obj_ownership = AccountOwnership.OWNER


class InvestmentPage(LoggedPage, HTMLPage):
    @method
    class iter_investment(TableElement):
        item_xpath = '//table/tbody/tr[td[2]]'
        head_xpath = '//table/thead//th'

        col_label = 'Nom des supports'
        col_valuation = re.compile('.*Montant')
        col_vdate = 'Date de valorisation'
        col_portfolio_share = 'Répartition'
        col_quantity = re.compile('Nombre de parts')
        col_unitvalue = re.compile('Valeur de la part')

        class item(ItemElement):
            klass = Investment

            obj_label = CleanText(TableCell('label'))
            obj_code = QueryValue(Link('.//a[contains(@href, "isin")]', default=''), 'isin', default=NotAvailable)

            def valuation(self):
                td = TableCell('valuation')(self)[0]
                return CleanDecimal('.')(td)

            def obj_quantity(self):
                if not self.page.is_detail():
                    return NotAvailable
                td = TableCell('quantity')(self)[0]
                return CleanDecimal('.//span[1]', replace_dots=True)(td)

            def obj_valuation(self):
                if self.obj_original_currency():
                    return NotAvailable
                return self.valuation()

            def obj_original_valuation(self):
                if self.obj_original_currency():
                    return self.valuation()
                return NotLoaded

            def obj_vdate(self):
                td = TableCell('vdate')(self)[0]
                txt = CleanText('./text()')(td)
                return Date('.', dayfirst=True, default=NotAvailable).filter(txt)

            def obj_code_type(self):
                lst = self.el.xpath('./th/a')
                if not lst:
                    return NotAvailable
                return Investment.CODE_TYPE_ISIN

            obj_code = Regexp(Link('./th/a', default=''), r'isin=(.{12})$', default=NotAvailable)

            def unitvalue(self):
                return CleanDecimal(TableCell('unitvalue'), replace_dots=True)(self)

            def obj_unitvalue(self):
                if not self.page.is_detail() or self.obj_original_currency():
                    return NotAvailable
                return self.unitvalue()

            def obj_original_unitvalue(self):
                if self.page.is_detail() and self.obj_original_currency():
                    return self.unitvalue()
                return NotLoaded

            def obj_portfolio_share(self):
                if self.page.is_detail():
                    return NotAvailable
                return Eval(lambda x: x / 100, CleanDecimal(TableCell('portfolio_share'), replace_dots=True))(self)

            def obj_original_currency(self):
                cur = Currency(TableCell('valuation'))(self)
                return cur if self.env['currency'] != cur else NotLoaded

    def detailed_view(self):
        return Attr('//button[contains(text(), "Vision détaillée")]', 'data-module-open-link--link', default=None)(self.doc)

    def is_detail(self):
        return bool(self.doc.xpath('//th[contains(text(), "Valeur de la part")]'))

    def get_quantity(self, investment_label):
        th_index_xpath = 'count(//table/thead//th[contains(text(), "%s")]/preceding-sibling::th)+1'
        label_index = int(self.doc.xpath(th_index_xpath % 'Nom des supports'))
        quantity_index = int(self.doc.xpath(th_index_xpath % 'Nombre de parts'))

        for row in self.doc.xpath('//table/tbody/tr[td[2]]'):
            if CleanText('td[%d]' % label_index)(row) == investment_label:
                # Two numbers separated by `-`
                return CleanDecimal.French(
                    Regexp(CleanText('td[%d]' % quantity_index), r'(.+) - .*', default=''),
                    default=NotAvailable,
                )(row)
        return NotAvailable


class InvestmentMonAxaPage(LoggedPage, HTMLPage):
    def get_performance_url(self):
        return Link('//a[contains(text(), "Performance")]', default=None)(self.doc)

    @method
    class iter_investment(TableElement):
        item_xpath = '//div[@id="tabVisionContrat"]/table/tbody/tr'
        head_xpath = '//div[@id="tabVisionContrat"]/table/thead//th'

        col_label = 'Nom'
        col_code = 'ISIN'
        col_asset_category = 'Catégorie'
        col_valuation = 'Montant'
        col_portfolio_share = 'Poids'

        class item(ItemElement):
            klass = Investment

            obj_label = CleanText(TableCell('label'))
            obj_code = IsinCode(CleanText(TableCell('code')), default=NotAvailable)
            obj_code_type = IsinType(CleanText(TableCell('code')))
            obj_asset_category = CleanText(TableCell('asset_category'))
            obj_valuation = CleanDecimal.French(TableCell('valuation'), default=NotAvailable)

            def obj_portfolio_share(self):
                share_percent = CleanDecimal.French(TableCell('portfolio_share'), default=None)(self)
                if not empty(share_percent):
                    return share_percent / 100
                return NotAvailable


class PerformanceMonAxaPage(LoggedPage, HTMLPage):
    def get_table_cell_xpath(self, table_id, inv_label, column_label, position_in_colspan=0):
        tr_position = 1
        ths = self.doc.xpath('//div[@id="%s"]/table//th' % table_id)
        for th in ths:
            if CleanText('.')(th) == column_label:
                break
            colspan = CleanText(Attr('.', 'colspan', default=''))(th)
            if colspan:
                tr_position += int(colspan)
            else:
                tr_position += 1
        tr_position += position_in_colspan

        return '//div[@id="%s"]/table//td[a/text()="%s"]/../td[position()=%s]' % (
            table_id,
            inv_label,
            tr_position,
        )

    @method
    class fill_investment(ItemElement):
        # The page contains several tables with different info for all investments
        def obj_vdate(self):
            return Date(
                CleanText(self.page.get_table_cell_xpath('tab-evolution-epargne', self.obj.label, 'Date')),
                dayfirst=True,
                default=NotAvailable,
            )(self)

        def obj_quantity(self):
            return CleanDecimal.French(
                self.page.get_table_cell_xpath('tab-evolution-epargne', self.obj.label, 'Nb parts'),
                default=NotAvailable,
            )(self)

        def obj_unitvalue(self):
            return CleanDecimal.French(
                self.page.get_table_cell_xpath('tab-evolution-epargne', self.obj.label, 'VL'),
                default=NotAvailable,
            )(self)

        def obj_unitprice(self):
            return CleanDecimal.French(
                self.page.get_table_cell_xpath('tab-evolution-epargne', self.obj.label, 'PMPA'),
                default=NotAvailable,
            )(self)

        def obj_diff(self):
            return CleanDecimal.French(
                self.page.get_table_cell_xpath('tab-evolution-epargne', self.obj.label, 'P/M Value (€, %)', 0),
                default=NotAvailable,
            )(self)

        def obj_diff_ratio(self):
            diff_percent = CleanDecimal.French(
                self.page.get_table_cell_xpath('tab-evolution-epargne', self.obj.label, 'P/M Value (€, %)', 1),
                default=None,
            )(self)
            if diff_percent is not None:
                return diff_percent / 100
            return NotAvailable

        def obj_performance_history(self):
            perfs = {}

            for year, label in {1: '1an', 3: '3 ans', 5: '5 ans'}.items():
                performance = CleanDecimal.French(
                    self.page.get_table_cell_xpath('tab-perf-cumulees', self.obj.label, label),
                    default=None,
                )(self)
                if performance is not None:
                    perfs[year] = performance / 100

            return perfs or NotAvailable

        def obj_srri(self):
            srri = Regexp(
                CleanText(self.page.get_table_cell_xpath('tab-risque', self.obj.label, 'SRRI')),
                r'(\d) /7',
                default=None,
            )(self)
            if srri:
                return int(srri)
            return NotAvailable


class Transaction(FrenchTransaction):
    PATTERNS = [
        (re.compile(r'^(?P<text>souscription.*)'), FrenchTransaction.TYPE_DEPOSIT),
        (re.compile(r'^(?P<text>.*)'), FrenchTransaction.TYPE_BANK),
    ]


class AccountDetailsPage(LoggedPage, HTMLPage):
    def get_account_url(self, url):
        return Attr('//a[@href="%s"]' % url, 'data-url')(self.doc)

    def get_investment_url(self):
        return Attr('//div[contains(@data-analytics-label, "repartition_par_fond")]', 'data-url', default=None)(self.doc)

    def get_iframe_url(self):
        return Attr('//div[contains(@class, "iframe-quantalys")]', 'data-module-iframe-quantalys--iframe-url', default=None)(self.doc)

    def get_pid(self):
        return Attr('//div[@data-module="operations-movements"]', 'data-module-operations-movements--pid', default=None)(self.doc)


class HistoryPage(LoggedPage, JsonPage):
    def has_operations(self):
        return Dict('response/operations')(self.doc)

    @method
    class iter_history(DictElement):
        item_xpath = 'response/operations'

        class item(ItemElement):
            klass = Transaction

            def condition(self):
                # Only return validated transactions
                return Dict('status')(self) == 'DONE'

            obj_raw = Transaction.Raw(Dict('label'))
            obj_date = Date(Dict('date'))
            obj_amount = Eval(float_to_decimal, Dict('net_amount/value'))
            obj_gross_amount = Eval(float_to_decimal, Dict('gross_amount/value'))
            obj_type = Transaction.TYPE_BANK

            # 'oid' is used to get the transaction's investments
            obj__oid = Dict('id')


class HistoryInvestmentsPage(LoggedPage, JsonPage):
    @method
    class iter_transaction_investments(DictElement):
        item_xpath = 'response/operationDetail/transaction_lines'

        class item(ItemElement):
            klass = Investment

            def condition(self):
                # Some lines don't even have a label, we skip them
                return Dict('fund_label', default=None)(self)

            obj_label = Dict('fund_label')
            obj_valuation = Eval(float_to_decimal, Dict('amount/value'))
            obj_unitvalue = Eval(float_to_decimal, Dict('fund_unit_value/value', default=None))
            obj_quantity = Eval(float_to_decimal, Dict('fund_shares_count/value', default=None))
            obj_vdate = Date(Dict('fund_unit_value/date', default=None), default=NotAvailable)

            def obj_portfolio_share(self):
                raw_value = Eval(float_to_decimal, Dict('percentage', default=None))(self)
                if empty(raw_value):
                    return NotAvailable
                return raw_value / 100

    def has_investments(self):
        return Dict('response/operationDetail/transaction_lines', default=None)(self.doc)


class ProfilePage(LoggedPage, HTMLPage):
    def get_profile(self):
        form = self.get_form(xpath='//div[@class="popin-card"]')

        profile = Person()

        profile.name = '%s %s' % (form['party.first_name'], form['party.preferred_last_name'])
        profile.address = '%s %s %s' % (form['mailing_address.street_line'], form['mailing_address.zip_postal_code'], form['mailing_address.locality'])
        profile.email = CleanText('//label[@class="email-editable"]')(self.doc)
        profile.phone = CleanText('//div[@class="info-title colorized phone-disabled"]//label', children=False)(self.doc)
        return profile
