# -*- coding: utf-8 -*-

# Copyright(C) 2010-2011 Nicolas Duhamel
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

from decimal import Decimal
from datetime import timedelta

from woob.capabilities.bank import CapBankTransferAddRecipient, Account, AccountNotFound, RecipientNotFound
from woob.capabilities.bank.wealth import CapBankWealth
from woob.capabilities.contact import CapContact
from woob.capabilities.bank import TransferBankError
from woob.capabilities.base import find_object, strict_find_object, NotAvailable
from woob.capabilities.profile import CapProfile
from woob.capabilities.bill import (
    CapDocument, Subscription, SubscriptionNotFound,
    Document, DocumentNotFound,
)
from woob.tools.backend import Module, BackendConfig
from woob.tools.value import ValueBackendPassword, Value, ValueTransient

from .browser import BPBrowser, BProBrowser


__all__ = ['BPModule']


class BPModule(
    Module, CapBankWealth, CapBankTransferAddRecipient,
    CapContact, CapProfile, CapDocument,
):

    NAME = 'bp'
    MAINTAINER = u'Nicolas Duhamel'
    EMAIL = 'nicolas@jombi.fr'
    VERSION = '3.1'
    DEPENDENCIES = ('linebourse',)
    LICENSE = 'LGPLv3+'
    DESCRIPTION = u'La Banque Postale'
    CONFIG = BackendConfig(
        ValueBackendPassword('login', label='Identifiant', regexp=r'\d{10}[a-zA-Z0-9]?', masked=False),
        ValueBackendPassword('password', label='Mot de passe', regexp=r'^(\d{6})$'),
        Value(
            'website', label='Type de compte', default='par',
            choices={'par': 'Particuliers', 'pro': 'Professionnels'}
        ),
        ValueTransient('request_information'),
        ValueTransient('code'),
        ValueTransient('resume'),
    )

    def create_default_browser(self):
        b = {'par': BPBrowser, 'pro': BProBrowser}

        self.BROWSER = b[self.config['website'].get()]

        return self.create_browser(
            self.config,
            self.config['login'].get(),
            self.config['password'].get(),
            weboob=self.weboob
        )

    def iter_accounts(self):
        return self.browser.get_accounts_list()

    def get_account(self, _id):
        return find_object(self.browser.get_accounts_list(), id=_id, error=AccountNotFound)

    def iter_history(self, account):
        return self.browser.get_history(account)

    def iter_coming(self, account):
        return self.browser.get_coming(account)

    def iter_investment(self, account):
        return self.browser.iter_investment(account)

    def iter_market_orders(self, account):
        return self.browser.iter_market_orders(account)

    def iter_transfer_recipients(self, origin_account):
        if self.config['website'].get() != 'par':
            raise NotImplementedError()
        if isinstance(origin_account, Account):
            origin_account = origin_account.id
        return self.browser.iter_recipients(origin_account)

    def init_transfer(self, transfer, **params):
        if self.config['website'].get() != 'par':
            raise NotImplementedError()

        if 'code' in params:
            return self.browser.validate_transfer_code(transfer, params['code'])
        elif 'resume' in params:
            return self.browser.end_with_polling(transfer)

        self.logger.info('Going to do a new transfer')
        account = strict_find_object(self.iter_accounts(), iban=transfer.account_iban)
        if not account:
            account = strict_find_object(self.iter_accounts(), id=transfer.account_id, error=AccountNotFound)

        if not account._has_transfer:
            raise TransferBankError("Le compte ne permet pas l'émission de virements")

        recipient = strict_find_object(self.iter_transfer_recipients(account.id), iban=transfer.recipient_iban)
        if not recipient:
            recipient = strict_find_object(
                self.iter_transfer_recipients(account.id),
                id=transfer.recipient_id,
                error=RecipientNotFound
            )

        amount = Decimal(transfer.amount).quantize(Decimal(10) ** -2)

        # format label like label sent by firefox or chromium browser
        transfer.label = transfer.label.encode('latin-1', errors="xmlcharrefreplace").decode('latin-1')

        return self.browser.init_transfer(account, recipient, amount, transfer)

    def transfer_check_label(self, old, new):
        old = old.encode('latin-1', errors="xmlcharrefreplace").decode('latin-1')
        return super(BPModule, self).transfer_check_label(old, new)

    def transfer_check_date(self, old_exec_date, new_exec_date):
        return old_exec_date <= new_exec_date <= old_exec_date + timedelta(days=2)

    def execute_transfer(self, transfer, **params):
        return self.browser.execute_transfer(transfer)

    def new_recipient(self, recipient, **params):
        return self.browser.new_recipient(recipient, **params)

    def iter_contacts(self):
        if self.config['website'].get() != 'par':
            raise NotImplementedError()

        return self.browser.get_advisor()

    def get_profile(self):
        return self.browser.get_profile()

    def get_document(self, _id):
        subscription_id = _id.split('_')[0]
        subscription = self.get_subscription(subscription_id)
        return find_object(self.iter_documents(subscription), id=_id, error=DocumentNotFound)

    def get_subscription(self, _id):
        return find_object(self.iter_subscription(), id=_id, error=SubscriptionNotFound)

    def iter_documents(self, subscription):
        if not isinstance(subscription, Subscription):
            subscription = self.get_subscription(subscription)

        return self.browser.iter_documents(subscription)

    def iter_subscription(self):
        return self.browser.iter_subscriptions()

    def download_document(self, document):
        if not isinstance(document, Document):
            document = self.get_document(document)
        if document.url is NotAvailable:
            return

        return self.browser.download_document(document)

    def iter_resources(self, objs, split_path):
        if Account in objs:
            self._restrict_level(split_path)
            return self.iter_accounts()
        if Subscription in objs:
            self._restrict_level(split_path)
            return self.iter_subscription()

    def iter_emitters(self):
        return self.browser.iter_emitters()
