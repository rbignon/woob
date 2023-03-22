# Copyright(C) 2022-2023 Powens
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

from woob.browser.pages import HTMLPage, LoggedPage, JsonPage
from woob.browser.elements import TableElement, ItemElement, method, DictElement
from woob.browser.filters.standard import (
    CleanText, CleanDecimal, Regexp, Field, Date,
    Currency, MapIn, Lower, Eval, Format, FromTimestamp,
)
from woob.browser.filters.html import TableCell
from woob.browser.filters.json import Dict
from woob.capabilities.base import NotAvailable, empty
from woob.capabilities.bank import Account, Loan
from woob.capabilities.bank.wealth import Investment
from woob.capabilities.profile import Person
from woob.tools.capabilities.bank.investments import IsinCode, IsinType
from woob.tools.capabilities.bank.transactions import FrenchTransaction
from woob.tools.json import json


class AuthPage(JsonPage):
    pass


class TokenPage(JsonPage):
    def get_token(self):
        return 'Bearer ' + self.doc['token']


class UserStatesPage(JsonPage):
    def is_strong_auth_required(self):
        return self.doc.get('state') == 'STRONG_AUTH_REQUIRED'


ACCOUNT_TYPES = {
    'courant': Account.TYPE_CHECKING,
    'ordinaire': Account.TYPE_CHECKING,
    'liquidités': Account.TYPE_CHECKING,
    'livret': Account.TYPE_SAVINGS,
    'ldds': Account.TYPE_SAVINGS,
    'logement': Account.TYPE_SAVINGS,
    'pea': Account.TYPE_PEA,
    'titres': Account.TYPE_MARKET,
    'crédit': Account.TYPE_LOAN,
    'bmoovie': Account.TYPE_LIFE_INSURANCE,
    'gestion vie': Account.TYPE_LIFE_INSURANCE,
    'prudent': Account.TYPE_LIFE_INSURANCE,
    'patrimoine': Account.TYPE_LIFE_INSURANCE,
    'epargne vie': Account.TYPE_LIFE_INSURANCE,
    'spirimmo': Account.TYPE_LIFE_INSURANCE,
    'espace invest': Account.TYPE_LIFE_INSURANCE,
    'banque privilege': Account.TYPE_REVOLVING_CREDIT,
    'pret personnel': Account.TYPE_LOAN,
}


class Transaction(FrenchTransaction):
    PATTERNS = [
        (re.compile(r'\w+ FRAIS RET DAB '), FrenchTransaction.TYPE_BANK),
        (
            re.compile(r'^RET DAB (?P<text>.*?) RETRAIT DU (?P<dd>\d{2})(?P<mm>\d{2})(?P<yy>\d{2}).*'),
            FrenchTransaction.TYPE_WITHDRAWAL,
        ),
        (re.compile(r'^RET DAB (?P<text>.*?) CARTE ?:.*'), FrenchTransaction.TYPE_WITHDRAWAL),
        (
            re.compile(r'^RET DAB (?P<dd>\d{2})/(?P<mm>\d{2})/(?P<yy>\d{2}) (?P<text>.*?) CARTE .*'),
            FrenchTransaction.TYPE_WITHDRAWAL,
        ),
        (
            re.compile(r'(?P<text>.*) RET DAB DU (?P<dd>\d{2})/(?P<mm>\d{2})/(?P<yy>\d{2}) (?P<text2>.*?) CARTE .*'),
            FrenchTransaction.TYPE_WITHDRAWAL,
        ),
        (
            re.compile(r'^(?P<text>.*) RETRAIT DU (?P<dd>\d{2})(?P<mm>\d{2})(?P<yy>\d{2}) .*'),
            FrenchTransaction.TYPE_WITHDRAWAL,
        ),
        (re.compile(r'^RET DAB'), FrenchTransaction.TYPE_WITHDRAWAL),
        (
            re.compile(r'(\w+) (?P<dd>\d{2})(?P<mm>\d{2})(?P<yy>\d{2}) CB[:*][^ ]+ (?P<text>.*)'),
            FrenchTransaction.TYPE_CARD,
        ),
        (
            re.compile(r'(?P<text>.*) ACHAT DU (?P<dd>\d{2})/(?P<mm>\d{2})/(?P<yy>\d{2}) CARTE .*'),
            FrenchTransaction.TYPE_CARD,
        ),
        (re.compile(r'^FAC ACH FR CB'), FrenchTransaction.TYPE_CARD),
        (re.compile(r'^FAC ACH ETR CB'), FrenchTransaction.TYPE_CARD),
        (
            re.compile(r'^(?P<category>VIR(EMEN)?T? (SEPA)?(RECU|FAVEUR)?)( /FRM)?(?P<text>.*)'),
            FrenchTransaction.TYPE_TRANSFER,
        ),
        (re.compile(r'^Virement'), FrenchTransaction.TYPE_TRANSFER),
        (re.compile(r'^Versement'), FrenchTransaction.TYPE_TRANSFER),
        (re.compile(r'^PRLV (?P<text>.*) (?:REF: \w+ DE (?P<text2>.*))?$'), FrenchTransaction.TYPE_ORDER),
        (re.compile(r'(PRELEVEMENT.|Pr.l.vements) (?P<text>.*)'), FrenchTransaction.TYPE_ORDER),
        (re.compile(r'^PRLV'), FrenchTransaction.TYPE_ORDER),
        (re.compile(r'^CHEQUE.*? (REF \w+)?$'), FrenchTransaction.TYPE_CHECK),
        (re.compile(r'^CHEQUE NO \d+'), FrenchTransaction.TYPE_CHECK),
        (re.compile(r'^CHQ (.+)'), FrenchTransaction.TYPE_CHECK),
        (re.compile(r'^(AGIOS /|FRAIS) (?P<text>.*)'), FrenchTransaction.TYPE_BANK),
        (re.compile(r'.*(CONVENTION \d+ )?COTIS(ATION)? (?P<text>.*)'), FrenchTransaction.TYPE_BANK),
        (re.compile(r'^REMISE (?P<text>.*)'), FrenchTransaction.TYPE_DEPOSIT),
        (re.compile(r'^REM .+ CHQ'), FrenchTransaction.TYPE_DEPOSIT),
        (re.compile(r'^(?P<text>.*)( \d+)? QUITTANCE .*'), FrenchTransaction.TYPE_ORDER),
        (re.compile(r'^.* LE (?P<dd>\d{2})/(?P<mm>\d{2})/(?P<yy>\d{2})$'), FrenchTransaction.TYPE_UNKNOWN),
        (re.compile(r'^CARTE .*'), FrenchTransaction.TYPE_CARD_SUMMARY),
        (re.compile(r'CONTRIBUTIONS SOCIALES'), FrenchTransaction.TYPE_BANK),
        (re.compile(r'(COMMISSION|Commission) .* (INTERVENTION|TRANSFERT|Change)'), FrenchTransaction.TYPE_BANK),
        (re.compile(r'Int.r.ts (cr.diteurs|d.biteurs).*'), FrenchTransaction.TYPE_BANK),
        (re.compile(r'INTERETS (CREDITEURS|ANNUELS)'), FrenchTransaction.TYPE_BANK),
        (re.compile(r'INT. CREDIT'), FrenchTransaction.TYPE_BANK),
        (re.compile(r'(ANNUL |ANNULATION |)FRAIS '), FrenchTransaction.TYPE_BANK),
        (re.compile(r'(ANNUL |ANNULATION |)INT DEB'), FrenchTransaction.TYPE_BANK),
        (re.compile(r'TAEG APPLIQUE '), FrenchTransaction.TYPE_BANK),
        (re.compile(r'ACHAT DEBIT DIFF.*'), FrenchTransaction.TYPE_DEFERRED_CARD),
        (re.compile(r'Retrait sur .*'), FrenchTransaction.TYPE_WITHDRAWAL),
    ]


class MilleisDictElement(ItemElement):
    klass = Account

    obj_label = CleanText(Dict('text'))

    def obj_id(self):
        cleaned_id = CleanText(Dict('number/value'), replace=[(' ', '')])(self)
        if Field('type')(self) == Account.TYPE_MARKET:
            return 'TTR' + cleaned_id
        return cleaned_id

    obj_balance = CleanDecimal.SI(Dict('balance/value'))
    obj_currency = Currency(Dict('currency/value'))
    obj_type = MapIn(Lower(Field('label')), ACCOUNT_TYPES, Account.TYPE_UNKNOWN)

    def obj_number(self):
        number = CleanText(Dict('number/value'))(self)
        return re.sub(r'[a-zA-Z]+', '', number)

    def obj__iter_history_id(self):
        return CleanText(Field('number'), replace=[(' ', '')])(self) + CleanText(Dict('currency/reference'))(self)

    obj__is_cash = False


class AccountsPage(LoggedPage, JsonPage):
    @method
    class iter_accounts(DictElement):
        # Some life insurance accounts can be duplicated in the json
        ignore_duplicate = True

        class item(MilleisDictElement):
            pass


class AccountsHistoryPage(LoggedPage, JsonPage):
    @method
    class iter_history(DictElement):

        class item(ItemElement):
            klass = Transaction

            obj_label = CleanText(Dict('text'))
            obj_raw = Transaction.Raw(Field('label'))
            obj_amount = CleanDecimal.SI(Dict('amount'))
            obj_date = FromTimestamp(Dict('operationTimestamp'), millis=True)


class CardsPage(LoggedPage, JsonPage):
    @method
    class iter_accounts(DictElement):

        class item(ItemElement):
            klass = Account

            def condition(self):
                return self.el['type'] == 'DEFERRED_DEBIT'

            obj_label = CleanText(Dict('brand/value'))
            obj_id = Format('%sCRT', Field('number'))
            obj_balance = CleanDecimal.SI(Dict('virtualAccount/balance/value'))
            obj_currency = Currency(Dict('currency/value'))
            obj_type = Account.TYPE_CARD
            obj_number = CleanText(Dict('encryptedNumber/value'))
            obj__reference = CleanText(Dict('encryptedNumber/reference'))
            obj__root = CleanText(Dict('currentAccount/customer/root'))
            obj__is_cash = False


class CardsHistoryPage(AccountsHistoryPage):
    pass


class CheckingAccountsPage(AccountsPage):
    pass


class SavingAccountsPage(AccountsPage):
    pass


class MarketAccountsPage(AccountsPage):
    @method
    class iter_cash_accounts(DictElement):
        item_xpath = '*/currentAccounts'

        class item(MilleisDictElement):
            obj__is_cash = True


class GetMarketURLPage(LoggedPage, JsonPage):
    def get_iter_invest_url(self):
        return self.doc['url']

    def get_iter_history_url(self):
        return self.doc['url']


class MarketInvestPage(LoggedPage, HTMLPage):
    @method
    class iter_investments(TableElement):
        head_xpath = '//table[@id="m-positions-data-table"]/thead/tr/th'
        item_xpath = '//table[@id="m-positions-data-table"]/tbody/tr'

        col_label = 'Valeur'
        col_quantity = re.compile(r'Q(uanti)?té')
        col_unitvalue = 'Cours'
        col_unitprice = 'PAM €'
        col_valuation = re.compile(r'Valo(risation|\.) €')
        col_portfolio_share = 'Poids %'
        col_raw_diff = '+/- Values'

        class item(ItemElement):
            klass = Investment

            def condition(self):
                return CleanDecimal.French(TableCell('valuation'), default=None)(self)

            # We catch the part of investment's label before the ISIN Code in the end of the label's string
            # ex: "ABIVAX FR0012333284"
            obj_label = Regexp(CleanText(TableCell('label')), r'(.+) \S+$')
            obj_code = IsinCode(
                CleanText('.//div[@class="nested"]//span[@class="subfield m_isin"]', default=NotAvailable),
                default=NotAvailable
            )
            obj_quantity = CleanDecimal.French(TableCell('quantity'), default=NotAvailable)
            obj_unitvalue = CleanDecimal.French(TableCell('unitvalue'), default=NotAvailable)
            obj_valuation = CleanDecimal.French(TableCell('valuation'), default=NotAvailable)
            obj_unitprice = CleanDecimal.French(TableCell('unitprice'), default=NotAvailable)
            obj_code_type = IsinType(Field('code'))
            obj_portfolio_share = Eval(
                lambda x: x / 100,
                CleanDecimal.French(TableCell('portfolio_share'))
            )

            def obj_diff(self):
                raw_diff = CleanText(TableCell('raw_diff', default=NotAvailable))(self)
                if not empty(raw_diff):
                    raw_diff = raw_diff.split('/')[0]
                    return CleanDecimal.French().filter(raw_diff)
                return NotAvailable

            def obj_diff_ratio(self):
                percent_diff = CleanText(TableCell('raw_diff', default=NotAvailable))(self)
                if not empty(percent_diff):
                    percent_diff = percent_diff.split('/')[1]
                    return CleanDecimal.French().filter(percent_diff)
                return NotAvailable


class MarketHistoryPage(LoggedPage, HTMLPage):
    @method
    class iter_history(TableElement):
        head_xpath = '//table[@id="m-movements-data-table"]/thead/tr/th'
        item_xpath = '//table[@id="m-movements-data-table"]/tbody/tr'

        col_label = 'Valeur'
        col_quantity = 'Qté'
        col_unitprice = 'Cours'
        col_valuation = 'Montant Net'
        col_vdate = 'Date'

        class item(ItemElement):
            klass = Transaction

            def condition(self):
                return not self.xpath('.//td[contains(.,"Pas de mouvements")]')

            # We catch the part of investment's label before the ISIN Code in the end of the label's string
            # ex: "ABIVAX FR0012333284"
            obj_label = Regexp(CleanText(TableCell('label')), r'(.+) \S+$')
            obj_amount = CleanDecimal.French(TableCell('valuation'))
            obj_date = Date(CleanText(TableCell('vdate')), dayfirst=True)
            obj_type = Transaction.TYPE_ORDER

            def obj_investments(self):
                i = Investment()
                i.label = Regexp(CleanText(TableCell('label')), r'(.+) \S+$')(self)
                i.code = IsinCode(
                    CleanText('.//div[@class="nested"]//span[@class="subfield m_isin"]', default=NotAvailable),
                    default=NotAvailable
                )(self)
                i.quantity = CleanDecimal.French(TableCell('quantity'))(self)
                i.valuation = Field('amount')(self)
                i.unitprice = CleanDecimal.French(TableCell('unitprice'), default=NotAvailable)(self)
                i.vdate = Field('date')(self)
                i.code_type = IsinCode(
                    CleanText('.//div[@class="nested"]//span[@class="subfield m_isin"]', default=NotAvailable),
                    default=NotAvailable
                )(self)
                return [i]


class LifeInsuranceAccountsPage(AccountsPage):
    pass


class LifeInsuranceHistoryPage(LoggedPage, JsonPage):
    @method
    class iter_investments(DictElement):
        item_xpath = 'supports'

        class item(ItemElement):
            klass = Investment

            obj_label = CleanText(Dict('title'))
            obj_quantity = CleanDecimal.SI(Dict('quantity'), default=NotAvailable)
            obj_unitvalue = CleanDecimal.SI(Dict('unitValue'), default=NotAvailable)
            obj_valuation = CleanDecimal.SI(Dict('valuation'))
            obj_code = NotAvailable


class LoanAccountsPage(AccountsPage):
    @method
    class iter_accounts(DictElement):

        class item(ItemElement):
            klass = Loan

            obj_label = CleanText(Dict('text'))
            obj_id = CleanText(Dict('number/value'), replace=[(' ', '')])
            obj_balance = CleanDecimal.SI(Dict('balance/value'))
            obj_currency = Currency(Dict('currency/value'))
            obj_type = MapIn(Lower(Field('label')), ACCOUNT_TYPES, Account.TYPE_UNKNOWN)
            obj_number = Field('id')
            obj__loan_details_id = CleanText(Dict('number/reference'))
            obj__is_cash = False


class LoanAccountsDetailsPage(AccountsPage):
    @method
    class fill_loan(ItemElement):
        obj_subscription_date = FromTimestamp(Dict('startTimestamp'), millis=True)
        obj_maturity_date = FromTimestamp(Dict('endTimestamp'), millis=True)
        obj_rate = CleanDecimal.SI(Dict('interestRate'))
        obj_last_payment_amount = CleanDecimal.SI(Dict('previousPaymentDueAmount'))
        obj_last_payment_date = FromTimestamp(Dict('previousPaymentDueTimestamp'), millis=True)
        obj_next_payment_amount = CleanDecimal.SI(Dict('nextPaymentDueAmount'))
        obj_next_payment_date = FromTimestamp(Dict('nextPaymentDueTimestamp'), millis=True)


class GetProfilePage(LoggedPage, JsonPage):
    def build_doc(self, content):
        return json.loads(content)

    @method
    class get_profile(ItemElement):
        klass = Person

        obj_name = CleanText(Dict('text'))
        obj_firstname = CleanText(Dict('firstName'))
        obj_lastname = CleanText(Dict('name'))
        obj_email = CleanText(Dict('email'))
        obj_gender = CleanText(Dict('title'))
