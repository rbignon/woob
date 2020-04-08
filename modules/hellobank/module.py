# -*- coding: utf-8 -*-

# Copyright(C) 2012-2020  Budget Insight
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

from weboob.capabilities.bank import (
    CapBankTransferAddRecipient, AccountNotFound, Account, RecipientNotFound,
    TransferInvalidLabel,
)
from weboob.capabilities.wealth import CapBankWealth
from weboob.capabilities.profile import CapProfile
from weboob.capabilities.base import find_object, strict_find_object
from weboob.tools.backend import Module, BackendConfig
from weboob.tools.value import ValueBackendPassword, ValueBool
from weboob.capabilities.bill import (
    Subscription, CapDocument, SubscriptionNotFound, DocumentNotFound, Document,
    DocumentTypes,
)

from .browser import HelloBank


__all__ = ['HelloBankModule']


class HelloBankModule(Module, CapBankWealth, CapBankTransferAddRecipient, CapProfile, CapDocument):
    NAME = 'hellobank'
    MAINTAINER = u'Romain Bignon'
    EMAIL = 'romain@weboob.org'
    VERSION = '2.1'
    LICENSE = 'AGPLv3+'
    DESCRIPTION = 'BNP Paribas'
    CONFIG = BackendConfig(
        ValueBackendPassword('login',      label=u'Numéro client', masked=False),
        ValueBackendPassword('password',   label=u'Code secret', regexp='^(\d{6})$'),
        ValueBool('rotating_password',     label=u'Automatically renew password every 100 connections', default=False),
        ValueBool('digital_key',           label=u'User with digital key have to add recipient with digital key', default=False))
    BROWSER = HelloBank

    accepted_document_types = (
        DocumentTypes.STATEMENT,
        DocumentTypes.REPORT,
        DocumentTypes.BILL,
        DocumentTypes.OTHER,
    )

    def create_default_browser(self):
        return self.create_browser(self.config, weboob=self.weboob)

    def iter_resources(self, objs, split_path):
        if Account in objs:
            self._restrict_level(split_path)
            return self.iter_accounts()
        if Subscription in objs:
            self._restrict_level(split_path)
            return self.iter_subscription()

    def iter_accounts(self):
        return self.browser.iter_accounts()

    def get_account(self, _id):
        account = self.browser.get_account(_id)
        if account:
            return account
        else:
            raise AccountNotFound()

    def iter_history(self, account):
        return self.browser.iter_history(account)

    def iter_coming(self, account):
        return self.browser.iter_coming_operations(account)

    def iter_investment(self, account):
        return self.browser.iter_investment(account)

    def iter_transfer_recipients(self, origin_account):
        if isinstance(origin_account, Account):
            origin_account = origin_account.id
        return self.browser.iter_recipients(origin_account)

    def new_recipient(self, recipient, **params):
        # Recipient label has max 70 chars.
        recipient.label = ' '.join(w for w in re.sub('[^0-9a-zA-Z-,\.: ]+', '', recipient.label).split())[:70]
        return self.browser.new_recipient(recipient, **params)

    def init_transfer(self, transfer, **params):
        if transfer.label is None:
            raise TransferInvalidLabel()

        self.logger.info('Going to do a new transfer')
        if transfer.account_iban:
            account = find_object(self.iter_accounts(), iban=transfer.account_iban, error=AccountNotFound)
        else:
            account = find_object(self.iter_accounts(), id=transfer.account_id, error=AccountNotFound)

        recipient = strict_find_object(self.iter_transfer_recipients(account.id), iban=transfer.recipient_iban)
        if not recipient:
            recipient = strict_find_object(self.iter_transfer_recipients(account.id), id=transfer.recipient_id, error=RecipientNotFound)

        assert account.id.isdigit()
        # quantize to show 2 decimals.
        amount = Decimal(transfer.amount).quantize(Decimal(10) ** -2)

        return self.browser.init_transfer(account, recipient, amount, transfer.label, transfer.exec_date)

    def execute_transfer(self, transfer, **params):
        return self.browser.execute_transfer(transfer)

    def transfer_check_recipient_id(self, old, new):
        # external recipient id can change, check the iban in recipient id
        iban = re.search(r'([A-Z]{2}[A-Z\d]+)', old)
        if iban:
            # external recipients id
            iban = iban.group(1)
            return iban in new
        else:
            # iternal recipients id
            return old == new

    def iter_transfers(self, account=None):
        return self.browser.iter_transfers(account)

    def get_profile(self):
        return self.browser.get_profile()

    def get_subscription(self, _id):
        return find_object(self.iter_subscription(), id=_id, error=SubscriptionNotFound)

    def iter_documents(self, subscription):
        if not isinstance(subscription, Subscription):
            subscription = self.get_subscription(subscription)

        return self.browser.iter_documents(subscription)

    def iter_subscription(self):
        return self.browser.iter_subscription()

    def get_document(self, _id):
        subscription_id = _id.split('_')[0]
        subscription = self.get_subscription(subscription_id)
        return find_object(self.iter_documents(subscription), id=_id, error=DocumentNotFound)

    def download_document(self, document):
        if not isinstance(document, Document):
            document = self.get_document(document)

        return self.browser.open(document.url).content

    def iter_emitters(self):
        return self.browser.iter_emitters()
