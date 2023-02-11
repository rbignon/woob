# -*- coding: utf-8 -*-

# Copyright(C) 2014 Budget Insight
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
from datetime import date
from decimal import Decimal

import requests

from woob.capabilities.base import NotAvailable, empty
from woob.capabilities.bank import Account
from woob.tools.capabilities.bank.transactions import FrenchTransaction, sorted_transactions
from woob.browser.pages import HTMLPage, LoggedPage, pagination, JsonPage
from woob.browser.elements import ListElement, ItemElement, method, DictElement
from woob.browser.filters.standard import (
    Env, CleanDecimal, CleanText, Field, Format,
    Currency, Date, QueryValue, Map, Coalesce,
)
from woob.browser.filters.html import Attr
from woob.browser.filters.json import Dict
from woob.exceptions import BrowserIncorrectPassword, BrowserUnavailable


class Transaction(FrenchTransaction):
    PATTERNS = [
        (re.compile(r'^(?P<text>Retrait .*?) - traité le \d+/\d+$'), FrenchTransaction.TYPE_WITHDRAWAL),
        # C R C A M is a bank it is hardcoded here because some client want it typed and it would be a mess to scrap it
        (
            re.compile(r'^(?P<text>(Prélèvement|Cotisation|C R C A M) .*?) - traité le \d+/\d+$'),
            FrenchTransaction.TYPE_ORDER,
        ),
        (
            re.compile(r"^(?P<text>(Frais sur achat à l'étranger|Facturation).*?) - traité le \d+/\d+$"),
            FrenchTransaction.TYPE_BANK,
        ),
        (re.compile(r'^Intérêts mensuels'), FrenchTransaction.TYPE_BANK),
        (
            re.compile(r'^(?P<text>(Avoir comptant|ANNULATION|Annulation) .*?) - traité le \d+/\d+$'),
            FrenchTransaction.TYPE_PAYBACK,
        ),
        (re.compile(r'^(?P<text>(RETRAIT )?DAB .*?) - traité le \d+/\d+$'), FrenchTransaction.TYPE_WITHDRAWAL),
        # some labels are really badly formed so the regex needs to be this nasty to catch all edge cases
        (
            re.compile(r'^(?P<text>.*?)(, taux de change de(.*)?)? - traité le( (\d+|/\d+)*$|$)'),
            FrenchTransaction.TYPE_CARD,
        ),
    ]


class ContextInitPage(JsonPage):
    def get_client_id(self):
        return self.doc['context']['client_id']

    def get_success_url(self):
        return self.doc['context']['success_url']

    def get_customer_session_id(self):
        return self.doc['context']['customer_session_id']

    def get_oauth_token(self):
        # Could be always null
        return Dict('context/oauth_token')(self.doc)

    def get_additionnal_inputs(self):
        return Dict('context/additionnal_inputs')(self.doc)

    def get_error(self):
        return Dict('context/errors/0/label', default=None)(self.doc)


class StepsMixin(object):
    def get_steps(self):
        return Dict(self.steps_path)(self.doc)

    def get_step_of(self, step_type):
        for step in self.get_steps():
            if step['type'] == step_type:
                return step


class SendRiskEvaluationPage(JsonPage):
    def get_niveau_authent(self):
        return Dict('evaluatedRisk/niveau_authent')(self.doc)

    def get_flow_id(self):
        return Dict('evaluatedRisk/flowid')(self.doc)

    def get_error(self):
        return Dict('evaluatedRisk/errors/0/label', default=None)(self.doc)


class SendUsernamePage(StepsMixin, JsonPage):
    steps_path = 'initAuthenticationFlow/steps'

    def get_error(self):
        return Dict('initAuthenticationFlow/errors/0/label', default=None)(self.doc)


class SendInitStepPage(StepsMixin, JsonPage):
    steps_path = 'initStep/steps'

    def get_extra_data(self):
        return Dict('initStep/extra_data/0')(self.doc)

    def get_error(self):
        return Dict('initStep/errors/0/label', default=None)(self.doc)


class SendCompleteStepPage(StepsMixin, JsonPage):
    steps_path = "completeAuthFlowStep/flow/steps"

    def get_status(self):
        return Dict('completeAuthFlowStep/flow/steps/0/status', default=None)(self.doc)

    def get_token(self):
        return Dict('completeAuthFlowStep/token')(self.doc)

    def get_error(self):
        return Dict('completeAuthFlowStep/errors/0/label', default=None)(self.doc)


class LoginPage(JsonPage):
    def get_context_token(self):
        return QueryValue(Dict('url', default=''), 'context_token', default=None)(self.doc)


class ChoicePage(LoggedPage, HTMLPage):
    def get_redirect_other_space(self):
        # On some accounts, there is multiple spaces, it seems that the previous way to handle
        # the second space is not working for all the different spaces. the link we get here is supposed
        # to redirect us to the good space.
        return re.search(r'"action", "(.*?)"', CleanText('//div[@class="conteneur"]/script')(self.doc)).group(1)

    def get_pages(self):
        for page_attrib in self.doc.xpath('//a[@data-site]/@data-site'):
            yield self.browser.open(
                '/site/s/login/loginidentifiant.html',
                data={'selectedSite': page_attrib},
            ).page


class OneySpacePage(LoggedPage):
    def get_site(self):
        return "oney"


class ClientPage(OneySpacePage, HTMLPage):
    is_here = "//div[@id='situation']"

    @method
    class iter_accounts(ListElement):
        item_xpath = '//div[@id="situation"]//div[@class="synthese-produit"]'

        class item(ItemElement):
            klass = Account

            obj_currency = 'EUR'
            obj_type = Account.TYPE_REVOLVING_CREDIT
            obj_label = Env('label')
            obj__num = Env('_num')
            obj_id = Env('id')
            obj_balance = Env('balance')
            obj__site = 'oney'

            def parse(self, el):
                self.env['label'] = CleanText('./h3/a')(self) or 'Carte Oney'
                self.env['_num'] = Attr(
                    '%s%s%s' % (
                        '//option[contains(text(), "',
                        Field('label')(self).replace('Ma ', ''),
                        '")]',
                    ), 'value', default='')(self)
                self.env['id'] = Format('%s%s' % (self.page.browser.username, Field('_num')(self)))(self)

                # On the multiple accounts page, decimals are separated with dots, and separated with commas on single account page.
                amount_due = CleanDecimal(
                    './p[@class = "somme-due"]/span[@class = "synthese-montant"]',
                    default=None
                )(self)
                if amount_due is None:
                    amount_due = CleanDecimal(
                        './div[@id = "total-sommes-dues"]/p[contains(text(), "sommes dues")]/span[@class = "montant"]',
                        replace_dots=True
                    )(self)
                self.env['balance'] = - amount_due


class OperationsPage(OneySpacePage, HTMLPage):
    is_here = "//div[@id='releve-reserve-credit'] | //div[@id='operations-recentes'] | //select[@id='periode']"

    @pagination
    @method
    class iter_transactions(ListElement):
        item_xpath = '//table[@class="tableau-releve"]/tbody/tr[not(node()//span[@class="solde-initial"])]'
        flush_at_end = True

        def flush(self):
            # As transactions are unordered on the page, we flush only at end
            # the sorted list of them.
            return sorted_transactions(self.objects.values())

        def store(self, obj):
            # It stores only objects with an ID. To be sure it works, use the
            # uid of transaction as object ID.
            obj.id = obj.unique_id(seen=self.env['seen'])
            return ListElement.store(self, obj)

        class credit(ItemElement):
            klass = Transaction
            obj_type = Transaction.TYPE_CARD
            obj_date = Transaction.Date('./td[1]')
            obj_raw = Transaction.Raw('./td[2]')
            obj_amount = Env('amount')

            def condition(self):
                self.env['amount'] = Transaction.Amount('./td[3]')(self.el)
                return self.env['amount'] > 0

        class debit(ItemElement):
            klass = Transaction
            obj_type = Transaction.TYPE_CARD
            obj_date = Transaction.Date('./td[1]')
            obj_raw = Transaction.Raw('./td[2]')
            obj_amount = Env('amount')

            def condition(self):
                self.env['amount'] = Transaction.Amount('', './td[4]')(self.el)
                return self.env['amount'] < 0

        def next_page(self):
            options = self.page.doc.xpath('//select[@id="periode"]//option[@selected="selected"]/preceding-sibling::option[1]')
            if options:
                data = {
                    'numReleve': options[0].values(),
                    'task': 'Releve',
                    'process': 'Releve',
                    'eventid': 'select',
                    'taskid': '',
                    'hrefid': '',
                    'hrefext': '',
                }
                return requests.Request("POST", self.page.url, data=data)


class ClientSpacePage(OneySpacePage, HTMLPage):
    # skip consumer credit, there is not enough information.
    # If an other type of page appear handle it here
    pass


class OtherSpaceMixin(object):
    def get_site(self):
        return "other"


class OtherSpaceJsonPage(LoggedPage, OtherSpaceMixin, JsonPage):
    def on_load(self):
        is_success = Dict('header/isSuccess', default=None)(self.doc)
        if not is_success:
            response_code = Dict('header/responseCode', default='')(self.doc)
            if 'InternalServerError' in response_code:
                # Seen when loading the dashboard. Not account listed when it happens.
                raise BrowserUnavailable()

            if 'Unauthorized' in response_code:
                response_message = Dict('header/responseMessage', default='')(self.doc)
                if 'INVALID_TOKEN' in response_message:
                    raise BrowserIncorrectPassword()
                raise AssertionError(f'Unhandled error message: {response_message}')

            if all([
                not Dict('content/header/isLoggedIn', default=None)(self.doc),
                'responseMessage' not in Dict('header', default=None)(self.doc),
            ]):
                # not logged-in and no message. this error is temporary.
                raise BrowserUnavailable()

            raise AssertionError(f'Unsuccessful request on : {self.url}')

        new_jwt_token = Dict('header/jwtToken/token', default=None)(self.doc)
        if new_jwt_token:
            self.browser.update_authorization(new_jwt_token)


class OAuthPage(OtherSpaceJsonPage):
    def get_headers_from_json(self):
        return {
            'Ino': Coalesce(
                Dict('userId', default=NotAvailable),
                Dict('personNumber', default=NotAvailable),
                Dict('ino', default=NotAvailable)
            )(self.doc),
            'IdentifierType': Dict('identifierType')(self.doc),
            'IsLoggedIn': Dict('content/header/isLoggedIn')(self.doc),
        }


class JWTTokenPage(JsonPage):
    def get_token(self):
        return Dict('token')(self.doc)


class OtherDashboardPage(OtherSpaceMixin, HTMLPage):
    def get_token(self):
        return QueryValue(None, 'token').filter(self.url)


OtherAccountTypeMap = {
    'RCP': Account.TYPE_CHECKING,
    'PP': Account.TYPE_LOAN,
    'GMP': Account.TYPE_LIFE_INSURANCE,
    'FP': Account.TYPE_LOAN,
}


class AccountsPage(OtherSpaceJsonPage):
    @method
    class iter_accounts(DictElement):
        item_xpath = 'content/body/dashboardContracts'

        class item(ItemElement):
            klass = Account

            obj__site = 'other'
            obj_currency = Currency(Dict('contract/currencyCode'))
            obj_type = Map(Dict('contract/typeCode'), OtherAccountTypeMap, default=Account.TYPE_UNKNOWN)
            obj_label = Dict('contract/displayableShortLabel')
            obj_number = Dict('contract/externalReference', default=NotAvailable)
            obj_id = Coalesce(
                Field('number'),
                Field('_guid'),
            )
            obj_balance = Decimal(0)

            def obj_coming(self):
                cur_type = Field('type')(self)
                if cur_type == Account.TYPE_LOAN:
                    return CleanDecimal.SI(
                        Dict('depreciableAccount/installments/0/totalAmount', default=0),
                        sign='-'
                    )(self)
                elif cur_type == Account.TYPE_CHECKING:
                    # Since it is a credit account, the amount are reversed.
                    return - CleanDecimal.SI(
                        Dict('contract/cashPaymentOutstandingAmount'),
                    )(self)
                else:
                    return NotAvailable

            def obj__guid(self):
                links_dict = {link['rel']: link for link in Dict('contract/links')(self)}
                if 'self' in links_dict:
                    return links_dict['self']['guid']
                elif 'depreciable_account' in links_dict:
                    return links_dict['depreciable_account']['guid']
                return NotAvailable


class OtherOperationsPage(OtherSpaceJsonPage):
    @method
    class iter_history(DictElement):
        item_xpath = 'content/body/transactions'

        class item(ItemElement):
            klass = Transaction

            def condition(self):
                # The website always display the transactions for all cards at the same time.
                # So we filter by account (guid).
                # The date is to separate between coming and transaction.
                trans_guid = Dict('contractGuid')(self)
                acc_guid = Env('guid')(self)
                guid_ok = trans_guid == acc_guid

                today = date.today()
                trans_date = Field('date')(self)
                if Env('is_coming')(self):
                    date_ok = trans_date >= today
                else:
                    date_ok = trans_date < today

                return date_ok and guid_ok

            obj_type = Transaction.TYPE_CARD
            obj_date = Date(Dict('transaction/date'))
            obj_raw = Transaction.Raw(Dict('transaction/displayableLabel'))

            def obj_amount(self):
                # Here we set a NotAvailable for default because there are transactions like 'Cotisation CB offerte'
                # that do not have amount but are still there on the website
                amount = CleanDecimal.SI(Dict('transaction/amount', default=None), default=None)(self)
                if empty(amount):
                    return NotAvailable
                return -amount
