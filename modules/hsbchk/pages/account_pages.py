# -*- coding: utf-8 -*-

# Copyright(C) 2010-2012 Julien Veyssier
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

from weboob.browser.elements import DictElement, ItemElement, method
from weboob.browser.filters.json import Dict
from weboob.browser.filters.standard import (
    CleanDecimal, CleanText, Date, Env, Eval, Field, Format, Map
)
from weboob.browser.pages import HTMLPage, LoggedPage, pagination, JsonPage
from weboob.capabilities.bank import Account
from weboob.exceptions import ActionNeeded, BrowserIncorrectPassword
from weboob.tools.capabilities.bank.transactions import FrenchTransaction


class Transaction(FrenchTransaction):
    PATTERNS = [
        (re.compile(r'^PAYMENT - THANK YOU'), FrenchTransaction.TYPE_CARD_SUMMARY),
        (re.compile(r'^CREDIT CARD PAYMENT (?P<text>.*)'), FrenchTransaction.TYPE_CARD_SUMMARY),
        (re.compile(r'^CREDIT INTEREST'), FrenchTransaction.TYPE_BANK),
        (re.compile(r'DEBIT INTEREST'), FrenchTransaction.TYPE_BANK),
        (re.compile(r'^UNAUTHORIZED OD CHARGE'), FrenchTransaction.TYPE_BANK),
        (re.compile(r'^ATM WITHDRAWAL\ *\((?P<dd>\d{2})(?P<mmm>\w{3})(?P<yy>\d{2})\)'), FrenchTransaction.TYPE_WITHDRAWAL),
        (re.compile(r'^POS CUP\ *\((?P<dd>\d{2})(?P<mmm>\w{3})(?P<yy>\d{2})\)\ *(?P<text>.*)'), FrenchTransaction.TYPE_CARD),
        (re.compile(r'^EPS\d*\ *\((?P<dd>\d{2})(?P<mmm>\w{3})(?P<yy>\d{2})\)\ *(?P<text>.*)'), FrenchTransaction.TYPE_CARD),
        (re.compile(r'^CR TO (?P<text>.*)\((?P<dd>\d{2})(?P<mmm>\w{3})(?P<yy>\d{2})\)'), FrenchTransaction.TYPE_TRANSFER),
        (re.compile(r'^FROM (?P<text>.*)\((?P<dd>\d{2})(?P<mmm>\w{3})(?P<yy>\d{2})\)'), FrenchTransaction.TYPE_TRANSFER),
    ]


class JsonBasePage(JsonPage):

    def on_load(self):
        coderet = Dict('responseInfo/reasons/0/code')(self.doc)
        conditions = (
                coderet == '000',
        )
        assert any(conditions), 'Error %s is not handled yet' % coderet


class JsonAccSum(LoggedPage, JsonBasePage):

    @method
    class iter_accounts(DictElement):
        def find_elements(self):
            for country in self.page.doc.get('countriesAccountList'):
                for acc in country.get('acctLiteWrapper'):
                    yield acc
                    for subacc in acc.get('subAcctInfo'):
                        yield subacc

        class item(ItemElement):
            klass = Account

            TYPES = {
                u"SAV": Account.TYPE_SAVINGS,
                u"CUR": Account.TYPE_CHECKING,
                u"TD": Account.TYPE_DEPOSIT,
                u"INV": Account.TYPE_MARKET,
                u"CC": Account.TYPE_CARD,
            }

            LABELS = {
                u"SAV": "Savings",
                u"CUR": "Current",
                u"TD": "Time deposit",
                u"INV": "Investment",
                u"CC": "Credit card",
            }

            def condition(self):
                return Dict('hasAcctDetails')(self)

            obj_bank_name = 'HSBC HK'
            obj_id = Format(
                '%s-%s-%s',
                Dict('displyID'),
                Dict('prodCatCde'),
                Dict('ldgrBal/ccy')
            )
            obj__idx = Dict('acctIndex')
            obj__entProdCatCde = Dict('entProdCatCde')
            obj__entProdTypCde = Dict('entProdTypCde')
            obj_number = Dict('displyID')
            obj_type = Map(Dict('prodCatCde'), TYPES, default=Account.TYPE_UNKNOWN)
            obj_label = Format(
                '%s %s',
                Map(Dict('prodCatCde'), LABELS),
                Dict('ldgrBal/ccy')
            )
            obj_currency = Dict('ldgrBal/ccy')
            obj_balance = CleanDecimal(Dict('ldgrBal/amt'))
            obj__nextstmt = None

class JsonAccDtl(LoggedPage, JsonBasePage):

    @method
    class fill_account(ItemElement):
            klass = Account

            obj__nextstmt = Date(Dict('ccAcctDtl/currStmtDetl/stmtDueDt'))
            obj_balance = CleanDecimal(Dict('ccAcctDtl/prevStmtDetl/primCrncyStmt/stmtAmt/amt'))
            obj_coming = Eval(
                lambda current, prev: current - prev,
                CleanDecimal(Dict('ccAcctDtl/ldgrBal/amt')),
                CleanDecimal(Dict('ccAcctDtl/prevStmtDetl/primCrncyStmt/stmtAmt/amt'))
            )

class JsonAccHist(LoggedPage, JsonBasePage):
    @pagination
    @method
    class iter_history(DictElement):

        item_xpath = "txnSumm"

        def next_page(self):
            if Dict('responsePagingInfo/moreRecords', default='N')(self.page.doc) == 'Y':
                self.logger.info("more values are available")
                """
                prev_req = self.page.response.request
                jq = json.loads(prev_req.body)
                jq['pagingInfo']['startDetail']=Dict('responsePagingInfo/endDetail')(self.page.doc)
                return requests.Request(
                    self.page.url,
                    headers = prev_req.headers,
                    json = jq
                )
                """
            return

        class item(ItemElement):
            klass = Transaction

            obj_rdate = Date(Dict('txnDate'))
            obj_vdate =  Date(Dict('txnPostDate'))

            def obj_date(self):
                if Dict('txnHistType', default=None)(self) == 'U':
                    return Env('nextstmt')(self)
                return Field('vdate')(self)

            obj_amount = CleanDecimal(Dict('txnAmt/amt'))

            def obj_raw(self):
                return Transaction.Raw(Dict('txnDetail/0'))(self)

            def obj_type(self):
                for pattern, type in Transaction.PATTERNS:
                    if pattern.match(Dict('txnDetail/0')(self)):
                        return type

                if Dict('txnHistType', default=None)(self) in ['U', 'B']:
                    return Transaction.TYPE_DEFERRED_CARD
                return Transaction.TYPE_TRANSFER


class AppGonePage(HTMLPage):
    def on_load(self):
        self.browser.app_gone = True
        self.logger.info('Application has gone. Relogging...')
        self.browser.do_logout()
        self.browser.do_login()


class OtherPage(HTMLPage):
    ERROR_CLASSES = [
        ('Votre contrat est suspendu', ActionNeeded),
        ("Vos données d'identification (identifiant - code secret) sont incorrectes", BrowserIncorrectPassword),
        ('Erreur : Votre contrat est clôturé.', ActionNeeded),
    ]

    def on_load(self):
        for msg, exc in self.ERROR_CLASSES:
            for tag in self.doc.xpath('//p[@class="debit"]//strong[text()[contains(.,$msg)]]', msg=msg):
                raise exc(CleanText('.')(tag))
