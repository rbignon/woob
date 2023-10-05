# -*- coding: utf-8 -*-

# Copyright(C) 2016      Edouard Lambert
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

import re
from decimal import Decimal

from woob.browser.pages import HTMLPage, JsonPage, LoggedPage, pagination
from woob.browser.elements import ItemElement, TableElement, DictElement, method
from woob.browser.filters.standard import (
    CleanDecimal, CleanText, Currency, Date,
    Eval, Field, Lower, MapIn, QueryValue, Regexp,
    Env, Base, Coalesce, Format,
)
from woob.browser.filters.json import Dict
from woob.browser.filters.html import Attr, Link, TableCell
from woob.capabilities.bank import Account, AccountOwnership
from woob.capabilities.bank.wealth import Investment
from woob.capabilities.profile import Person
from woob.capabilities.base import NotAvailable, NotLoaded, empty
from woob.tools.capabilities.bank.investments import IsinCode, IsinType
from woob.tools.capabilities.bank.transactions import Transaction as BankTransaction, FrenchTransaction
from woob.browser.pages import PartialHTMLPage, RawPage


def float_to_decimal(f):
    if empty(f):
        return NotAvailable
    return Decimal(str(f))


class HomePage(LoggedPage, PartialHTMLPage):
    pass


class InsuranceAccountsBouncerPage(LoggedPage, RawPage):
    pass


class ClearSessionPage(LoggedPage, RawPage):
    pass


class AccountsPage(LoggedPage, JsonPage):
    @method
    class iter_accounts(DictElement):
        item_xpath = 'activeAndTerminatedPolicies/activePolicies'

        class item(ItemElement):
            klass = Account

            def condition(self):
                # Filter out closed accounts and accounts without balance
                return CleanText(Dict('mainInfo'), default=None) and CleanText(Dict('status')) != 'TERMINATED'

            TYPES = {
                'assurance vie': Account.TYPE_LIFE_INSURANCE,
                'perp': Account.TYPE_PERP,
                'epargne retraite agipi pair': Account.TYPE_PERP,
                'epargne retraite agipi far': Account.TYPE_MADELIN,
                'epargne retraite ma retraite': Account.TYPE_PER,
                'epargne retraite far per': Account.TYPE_PER,
                'novial avenir': Account.TYPE_MADELIN,
                'epargne retraite novial': Account.TYPE_LIFE_INSURANCE,
            }

            obj_id = CleanText(Dict('subTitle'))
            obj_number = obj_id
            obj_label = CleanText(Dict('title'))
            obj_balance = CleanDecimal.SI(Dict('mainInfo'), default=None)
            obj_currency = Currency(CleanText(Dict('mainInfo'), default=None))
            obj__acctype = "investment"
            obj_type = MapIn(Lower(Field('label')), TYPES, Account.TYPE_UNKNOWN)
            obj__pid = CleanText(Dict('policyId'))
            obj__aid = CleanText(Dict('advisorId'))
            obj_url = Format(
                '/content/espace-client/accueil/savings/retirement/contract.content-inner.pid_%s.aid_%s.html',
                Field('_pid'),
                Field('_aid'),
            )

            obj_ownership = AccountOwnership.OWNER


class InvestmentErrorPage(LoggedPage, RawPage):
    pass


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
            obj_code_type = IsinType(Field('code'))
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

        return '//div[@id="%s"]/table//td[a[normalize-space()="%s"]]/../td[position()=%s]' % (
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


class InvestmentJsonPage(LoggedPage, JsonPage):
    def is_error(self):
        return Dict('status')(self.doc) == 'ERROR'

    @method
    class iter_investments(DictElement):
        item_xpath = 'response/funds'

        class item(ItemElement):
            klass = Investment

            obj_label = CleanText(Dict('label'))

            def obj_quantity(self):
                if Field('asset_category')(self) != 'EURO':
                    return CleanDecimal.SI(Dict('sharesCount'))(self)
                return NotAvailable

            def obj_unitvalue(self):
                if Field('asset_category')(self) not in ('EURO', 'FDCR'):
                    return CleanDecimal.SI(Dict('unitValue'))(self)
                return NotAvailable

            obj_valuation = CleanDecimal.SI(Dict('savingsAmount/value'))
            obj_vdate = Date(
                CleanText(
                    Dict('savingsAmount/date', default='')
                ),
                dayfirst=True,
                default=NotAvailable
            )
            obj_portfolio_share = CleanDecimal.SI(Dict('percentagePolicy'))
            obj_asset_category = CleanText(Dict('type'))


class Transaction(FrenchTransaction):
    PATTERNS = [
        (re.compile(r'^(?P<text>souscription.*)'), FrenchTransaction.TYPE_DEPOSIT),
        (re.compile(r'^(?P<text>.*)'), FrenchTransaction.TYPE_BANK),
    ]


class AccountDetailsPage(LoggedPage, HTMLPage):
    def get_real_account_url(self):
        return Attr('//div[contains(@class, "mawa-cards-item")]', 'data-url')(self.doc)

    def get_account_url(self, url):
        return Attr('//a[@href="%s"]' % url, 'data-url')(self.doc)

    def get_investment_url(self):
        return Attr('//div[contains(@data-analytics-label, "repartition_par_fond")]', 'data-url', default=None)(self.doc)

    def get_iframe_url(self):
        return Attr('//div[contains(@class, "iframe-quantalys")]', 'data-module-iframe-quantalys--iframe-url', default=None)(self.doc)

    def get_pid(self):
        return Attr('//div[@data-module="operations-movements"]', 'data-module-operations-movements--pid', default=None)(self.doc)

    def get_pid_invest(self, acc_number):
        return Attr(
            '//div[contains(@data-module-card-warning-banner--pid, "%s")]' % acc_number,
            'data-module-card-warning-banner--pid',
            default=None
        )(self.doc)


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
    @method
    class get_profile(ItemElement):
        klass = Person

        obj_firstname = CleanText(Attr('//input[@name="party.first_name"]', 'value'))
        obj_lastname = CleanText(Attr('//input[@name="party.preferred_last_name"]', 'value'))
        obj_email = CleanText(
            Attr(
                '//form[@data-module-input-editable--field-type="email"]',
                'data-module-input-editable--initial-input-value'
            )
        )


class OutremerProfilePage(ProfilePage):
    pass


class AccessBoursePage(JsonPage):
    def get_cypher(self):
        return self.doc['cypher']


class BourseAccountsPage(LoggedPage, HTMLPage):
    def get_cipher(self, account_number):
        return QueryValue(
            Link('.//a[contains(text(), "%s")]' % account_number),
            'cipher'
        )(self.doc)


class WealthHistoryPage(LoggedPage, HTMLPage):
    pass


class FormHistoryPage(LoggedPage, HTMLPage):
    @pagination
    @method
    class iter_history(TableElement):

        head_xpath = '//table[@id="histo"]/thead/tr/th/a'
        item_xpath = '//table[@id="histo"]/tbody/tr'

        col_date = 'Date comptable'
        col_label = 'Libellé opération'
        col_isin_code = re.compile('.*ISIN.*')
        col_quantity = 'Quantité'
        col_value = 'Cours'

        def next_page(self):
            url = Regexp(
                Attr('//a[contains(text(), "Suivant")]', 'onclick', default=''),
                r'{href: "(.+)"',
                default=NotAvailable,
            )(self)

            if url:
                return self.page.browser.build_request(url, method='POST')

        class item(ItemElement):
            klass = BankTransaction

            obj_raw = FrenchTransaction.Raw(TableCell('label'))
            obj_date = Date(CleanText(TableCell('date')), dayfirst=True)

            def obj_investments(self):
                # List of all investments of this account
                investments = Env('investments')(self)
                # Isin Code of the investment that the current transaction is about
                isin_code = IsinCode(
                    # Isin is located in an <a> tag, inside the <tr> tag
                    Base(TableCell('isin_code'), CleanText('.//a')),
                    default=NotAvailable,
                )(self)

                # Either the transaction match an existing investment, or we return an empty object
                return investments.get(isin_code, [])

    def has_more_transactions(self):
        return Coalesce(
            CleanText('//tr[@class="odd"]/td'),
            CleanText('//tr[@class="even"]/td'),
            default=None,
        )(self.doc)


class NewInvestmentPage(LoggedPage, HTMLPage):

    @method
    class iter_investments(TableElement):
        head_xpath = '//table[@id="valuation"]/thead/tr/th/a'
        item_xpath = '//table[@id="valuation"]/tbody/tr'

        col_isin_code = 'Code ISIN'
        col_label = re.compile(r'Libellé valeur.*')
        col_quantity = 'Quantité'
        col_unitprice = 'Prix de revient'
        col_unitvalue = re.compile('^Cours')
        col_valuation = re.compile('.*Valorisation.*')
        col_diff = re.compile('.*values latentes')

        class item(ItemElement):
            klass = Investment

            def condition(self):
                return CleanText(TableCell('label'))(self)

            # we can have isincode with a letter in its 10 last characters
            obj_code = IsinCode(
                Regexp(
                    CleanText(TableCell('isin_code')),
                    r'[A-Z]{2}[A-Z0-9]{10}',
                    default=NotAvailable
                ),
                default=NotAvailable
            )
            obj_code_type = IsinType(Field('code'))
            obj_label = CleanText(TableCell('label'))
            obj_quantity = CleanDecimal.French(TableCell('quantity'), default=NotAvailable)
            obj_unitprice = CleanDecimal.French(TableCell('unitprice'), default=NotAvailable)
            obj_unitvalue = CleanDecimal.French(TableCell('unitvalue'), default=NotAvailable)
            obj_valuation = CleanDecimal.French(TableCell('valuation'))
            obj_diff = CleanDecimal.French(TableCell('diff'))
