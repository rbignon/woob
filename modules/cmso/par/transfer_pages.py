# -*- coding: utf-8 -*-

# Copyright(C) 2019      Sylvie Ye
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

# flake8: compatible

from __future__ import unicode_literals

from hashlib import md5
import datetime as dt

from weboob.browser.pages import JsonPage, LoggedPage
from weboob.browser.elements import DictElement, ItemElement, method
from weboob.browser.filters.standard import (
    CleanText, Currency, CleanDecimal, Env,
    Format, Upper,
)
from weboob.browser.filters.json import Dict
from weboob.capabilities.bank import Recipient, Transfer, TransferBankError, Emitter
from weboob.capabilities.base import NotAvailable


class RecipientsListPage(LoggedPage, JsonPage):
    @method
    class iter_ext_recipients(DictElement):
        class item(ItemElement):
            klass = Recipient

            obj_category = 'Externe'
            obj_id = CleanText(Dict('id'))
            obj_label = obj__owner_name = CleanText(Dict('ownerName'))
            obj__bic = Dict('bic')
            obj__ciphered_iban = Dict('cipheredIban')
            # 'country' is a dict formatted like that:
            # {"code": "FR", "name": "France", "sepa": true}
            obj__country = Dict('country')
            # The iban has its last 5 numbers hidden
            obj_iban = NotAvailable
            obj__hidden_iban = Dict('iban')
            obj_bank_name = NotAvailable
            obj_enabled_at = dt.date.today()

    @method
    class iter_int_recipients(DictElement):
        class item(ItemElement):
            klass = Recipient

            def condition(self):
                # availableForCredit or availableForDebit
                return Dict(Format(
                    'availableFor%s',
                    Env('availableFor', default='Credit')
                ))(self)

            def obj_id(self):
                # There is nothing beside the account label and owner name
                # that we can use to create an unique id.
                to_hash = '%s %s' % (
                    Upper(Dict('label'))(self),
                    ''.join(sorted(CleanText(Dict('personName'))(self))),
                )
                return md5(to_hash.encode('utf-8')).hexdigest()

            obj_category = 'Interne'
            obj_label = CleanText(Dict('label'))
            obj__bic = Dict('bic')
            obj__owner_name = CleanText(Dict('personName'))
            obj__ciphered_iban = Dict('cipheredIban')
            obj__ciphered_contract_number = Dict('cipheredContractNumber')
            # The iban has its last 5 numbers hidden
            obj_iban = NotAvailable
            obj_enabled_at = dt.date.today()
            obj__type = CleanText(Dict('type'))


class AllowedRecipientsPage(LoggedPage, JsonPage):
    def get_allowed_contract_numbers(self):
        return self.text


class TransferInfoPage(LoggedPage, JsonPage):
    def get_transfer_info(self, info):
        # If account information is not available when asking for the
        # recipients (server error for ex.), return an empty dictionary
        # that will be filled later after being returned the json of the
        # account page (containing the accounts IDs too).
        if 'listCompteTitulaireCotitulaire' not in self.doc and 'exception' in self.doc:
            return {}

        information = {
            'numbers': ('index', 'numeroContratSouscrit'),
            'eligibilite_debit': ('numeroContratSouscrit', 'eligibiliteDebit'),
        }
        key = information[info][0]
        value = information[info][1]

        ret = {}
        ret.update({
            d[key]: d.get(value)
            for d in self.doc['listCompteTitulaireCotitulaire']
        })
        ret.update({
            d[key]: d.get(value)
            for p in self.doc['listCompteMandataire'].values()
            for d in p
        })
        ret.update({
            d[key]: d.get(value)
            for p in self.doc['listCompteLegalRep'].values()
            for d in p
        })
        return ret

    def get_numbers(self):
        transfer_numbers = self.get_transfer_info('numbers')
        for key, value in transfer_numbers.items():
            assert value, "The 'numeroContratSouscrit' associated with the account index: %s is empty" % key
        return transfer_numbers

    def get_eligibilite_debit(self):
        return self.get_transfer_info('eligibilite_debit')

    def check_response(self):
        return 'exception' not in self.doc

    @method
    class iter_emitters(DictElement):
        def parse(self, el):
            self.item_xpath = "%s/*" % Env('key')(self)

        def find_elements(self):
            selector = self.item_xpath.split('/')
            for sub_element in selector:
                if isinstance(self.el, dict) and self.el and sub_element == '*':
                    # data is sometimes found in sub dicts
                    self.el = [sub_list for sub_dict in self.el.values() for sub_list in sub_dict]
                if sub_element == '*':
                    continue
                self.el = self.el[sub_element]
            for sub_element in self.el:
                yield sub_element

        class item(ItemElement):
            klass = Emitter

            def condition(self):
                return Dict('eligibiliteDebit', default=None)(self.el)

            obj_id = Dict('numeroContratSouscrit')
            obj_label = Upper(Dict('lib'))
            obj_currency = Currency(Dict('deviseCompteCode'))

            def obj_balance(self):
                if 'solde' in self.el:
                    return CleanDecimal(Dict('solde'))(self)
                return NotAvailable


class TransferPage(LoggedPage, JsonPage):
    def on_load(self):
        if self.doc.get('exception') and not self.doc.get('debitAccountOwner'):
            if Dict('exception/type')(self.doc) == 1:
                # technical error
                raise AssertionError(
                    'Error with code %s occured during init_transfer: %s'
                    % (Dict('exception/code')(self.doc), Dict('exception/message')(self.doc))
                )
            elif Dict('exception/type')(self.doc) == 2:
                # user error
                raise TransferBankError(message=Dict('exception/message')(self.doc))

    def get_transfer_with_response(self, account, recipient, amount, reason, exec_date):
        transfer = Transfer()

        transfer.amount = CleanDecimal(Dict('amount/value'))(self.doc)
        transfer.currency = Currency(Dict('amount/currencyCode'))(self.doc)
        transfer.label = reason

        if exec_date:
            transfer.exec_date = dt.date.fromtimestamp(int(Dict('executionDate')(self.doc)) // 1000)

        transfer.account_id = account.id
        transfer.account_label = CleanText(Dict('debitAccount/name'))(self.doc)
        transfer.account_balance = account.balance

        transfer.recipient_id = recipient.id
        transfer.recipient_iban = recipient.iban
        transfer.recipient_label = CleanText(Dict('creditAccount/name'))(self.doc)

        return transfer

    def get_transfer_id(self):
        return CleanText(Dict('id'))(self.doc)
