# -*- coding: utf-8 -*-

# Copyright(C) 2021 Damien Ramelet.
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

import json
import re
from base64 import b64decode
from datetime import datetime

from dateutil import tz

from woob.browser.elements import DictElement, ItemElement, method
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import CleanDecimal, Date, Eval
from woob.browser.pages import JsonPage, LoggedPage
from woob.capabilities.bank import Account, AccountType
from woob.capabilities.bank.transfer import Recipient
from woob.tools.capabilities.bank.transactions import FrenchTransaction


class CustomJsonPage(JsonPage):
    def build_doc(self, content):
        # For 200 or 204 status code
        # Helios API can return an empty string
        # that doesn't follow JSON standard
        # Hence this hack
        if content == '':
            return json.dumps(content)
        return super(CustomJsonPage, self).build_doc(content)


class TokenPage(CustomJsonPage):
    @property
    def access_token(self):
        return Dict('accessToken')(self.doc)

    @property
    def refresh_token(self):
        return Dict('refreshToken')(self.doc)

    def compute_expire(self):
        payload = self.access_token.split('.')[1]
        decode = json.loads(b64decode(payload))
        # Helios implicitely provide timestamp with the 'Europe/Paris' timezone
        # Hence the conversion to UTC
        return datetime.utcfromtimestamp(
            decode['exp']
        ).replace(tzinfo=tz.gettz('UTC'))


class LoginPage(TokenPage):
    pass


class AccountsPage(LoggedPage, CustomJsonPage):
    def iter_accounts(self):
        """For now, Helios only provide checking account."""

        account = Account()
        account.balance = Eval(lambda x: x / 100, CleanDecimal(Dict('balance')))(self.doc)  # Amounts provided by the API are multiply by 100
        account.type = AccountType.CHECKING
        account.label = "Compte courant"

        return account


class Transaction(FrenchTransaction):
    PATTERNS = [
        (re.compile(r'.*SEPA.*'), FrenchTransaction.TYPE_TRANSFER),
        (re.compile(r'.*PURCHASE.*'), FrenchTransaction.TYPE_CARD),
        (re.compile(r'.*CHARGE_ACCOUNT.*'), FrenchTransaction.TYPE_BANK),
    ]


class TransactionsPage(LoggedPage, CustomJsonPage):
    @method
    class iter_history(DictElement):

        class item(ItemElement):
            klass = Transaction

            obj_date = Date(Dict('bookingDate'))
            obj_raw = Transaction.Raw(Dict('type'))
            obj_label = Dict('description')

            def obj_amount(self):
                return Eval(lambda x: x / 100, CleanDecimal(Dict('amount')))(self)


class BankDetailsPage(LoggedPage, CustomJsonPage):
    @property
    def iban(self):
        return Dict('iban')(self.doc)


class BeneficiariesPage(LoggedPage, CustomJsonPage):

    def get_recipient(self, recipient_id):
        for recipient in self.iter_beneficiaries():
            if recipient_id == recipient.id:
                return recipient

    @method
    class iter_beneficiaries(DictElement):
        class item(ItemElement):
            klass = Recipient

            obj_id = obj_iban = Dict('iban')
            obj_label = Dict('label')
            obj_enabled_at = Date(Dict('creation'))


class ProfilePage(LoggedPage, CustomJsonPage):
    pass


class RefreshTokenPage(TokenPage):
    pass


class TransferPage(LoggedPage, CustomJsonPage):
    def get_transfer_id(self):
        return Dict('id')(self.doc)

    def get_status(self):
        return Dict('status')(self.doc)

    def get_transfer_type(self):
        return Dict('transferType')(self.doc)


class ConfirmTransferPage(LoggedPage, CustomJsonPage):
    pass
