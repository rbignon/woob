# -*- coding: utf-8 -*-

# Copyright(C) 2012-2017 Romain Bignon
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
from decimal import Decimal

from woob.capabilities.bank import CapBankTransferAddRecipient, AccountNotFound, Account, RecipientNotFound
from woob.capabilities.bank.wealth import CapBankWealth
from woob.capabilities.bill import (
    CapDocument, Subscription, Document, DocumentNotFound, DocumentTypes,
)
from woob.capabilities.contact import CapContact
from woob.capabilities.profile import CapProfile
from woob.capabilities.base import find_object
from woob.tools.backend import Module, BackendConfig
from woob.tools.value import Value, ValueBackendPassword, ValueTransient

from .proxy_browser import ProxyBrowser

__all__ = ['CaisseEpargneModule']


class CaisseEpargneModule(Module, CapBankWealth, CapBankTransferAddRecipient, CapDocument, CapContact, CapProfile):
    NAME = 'caissedepargne'
    MAINTAINER = 'Romain Bignon'
    EMAIL = 'romain@weboob.org'
    VERSION = '3.4'
    DEPENDENCIES = ('linebourse',)
    DESCRIPTION = 'Caisse d\'Épargne'
    LICENSE = 'LGPLv3+'
    BROWSER = ProxyBrowser

    auth_type = {
        'part': 'Particulier',
        'pp': 'Personne protégée',
        'pro': 'Professionnel',
        'ent': 'Entreprise',
    }
    CONFIG = BackendConfig(
        ValueBackendPassword('login', label='Identifiant client', masked=False),
        ValueBackendPassword('password', label='Mot de passe', regexp=r'\d+'),
        Value('nuser', label='User ID (optional)', default='', regexp=r'[A-Z0-9]{0,8}'),
        Value('auth_type', label='Type de compte', choices=auth_type, default=''),
        ValueTransient('otp_emv', regexp=r'\d{8}'),
        ValueTransient('otp_sms', regexp=r'\d{8}'),
        ValueTransient('resume'),
        ValueTransient('request_information'),
    )

    accepted_document_types = (
        DocumentTypes.STATEMENT, DocumentTypes.OTHER, DocumentTypes.NOTICE,
    )

    def create_default_browser(self):
        return self.create_browser(
            nuser=self.config['nuser'].get(),
            config=self.config,
            username=self.config['login'].get(),
            password=self.config['password'].get(),
            woob=self.woob
        )

    # CapBank
    def iter_accounts(self):
        for account in self.browser.get_accounts_list():
            yield account
        for account in self.browser.get_loans_list():
            yield account

    def get_account(self, _id):
        return find_object(self.iter_accounts(), id=_id, error=AccountNotFound)

    def iter_history(self, account):
        return self.browser.get_history(account)

    def iter_coming(self, account):
        return self.browser.get_coming(account)

    # CapBankWealth
    def iter_investment(self, account):
        return self.browser.get_investment(account)

    def iter_market_orders(self, account):
        return self.browser.iter_market_orders(account)

    def iter_contacts(self):
        return self.browser.get_advisor()

    def get_profile(self):
        return self.browser.get_profile()

    # CapBankTransfer
    def iter_transfer_recipients(self, origin_account):
        if not isinstance(origin_account, Account):
            origin_account = self.get_account(origin_account)
        return self.browser.iter_recipients(origin_account)

    def init_transfer(self, transfer, **params):
        if {"otp_sms", "otp_emv", "resume"} & set(params.keys()):
            return self.browser.otp_validation_continue_transfer(transfer, **params)

        self.logger.info('Going to do a new transfer')
        transfer.label = re.sub(r"[^0-9A-Z/?:().,'+ -]+", '', transfer.label.upper())
        transfer.label = re.sub(r'\s+', ' ', transfer.label)
        if transfer.account_iban:
            account = find_object(self.iter_accounts(), iban=transfer.account_iban, error=AccountNotFound)
        else:
            account = find_object(self.iter_accounts(), id=transfer.account_id, error=AccountNotFound)

        if transfer.recipient_iban:
            recipient = find_object(
                self.iter_transfer_recipients(account.id), iban=transfer.recipient_iban,
                error=RecipientNotFound
            )
        else:
            recipient = find_object(
                self.iter_transfer_recipients(account.id), id=transfer.recipient_id,
                error=RecipientNotFound
            )

        transfer.amount = transfer.amount.quantize(Decimal(10) ** -2)

        return self.browser.init_transfer(account, recipient, transfer)

    def execute_transfer(self, transfer, **params):
        return self.browser.execute_transfer(transfer)

    def new_recipient(self, recipient, **params):
        return self.browser.new_recipient(recipient, **params)

    # mixed
    def iter_resources(self, objs, split_path):
        if Account in objs:
            self._restrict_level(split_path)
            return self.iter_accounts()
        if Subscription in objs:
            self._restrict_level(split_path)
            return self.iter_subscription()

    # CapDocument
    def get_document(self, _id):
        subscription_id = _id.split('_')[0]
        subscription = self.get_subscription(subscription_id)
        return find_object(self.iter_documents(subscription), id=_id, error=DocumentNotFound)

    def iter_subscription(self):
        return self.browser.iter_subscription()

    def iter_documents(self, subscription):
        if not isinstance(subscription, Subscription):
            subscription = self.get_subscription(subscription)

        return self.browser.iter_documents(subscription)

    def download_document(self, document):
        if not isinstance(document, Document):
            document = self.get_document(document)

        return self.browser.download_document(document)

    # CapTransfer
    def iter_transfers(self, account):
        for tr in self.browser.iter_transfers(account):
            if account and account.id != tr.account_id:
                continue
            yield tr

    def iter_emitters(self):
        return self.browser.iter_emitters()
