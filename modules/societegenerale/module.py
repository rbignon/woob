# -*- coding: utf-8 -*-

# Copyright(C) 2010-2011 Jocelyn Jaubert
# Copyright(C) 2012-2013 Romain Bignon
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
from datetime import timedelta

from unidecode import unidecode

from woob.capabilities.bank import (
    CapBankTransferAddRecipient, AccountNotFound,
    Account, RecipientNotFound,
)
from woob.capabilities.bank.pfm import CapBankMatching
from woob.capabilities.bill import (
    CapDocument, Subscription, Document, DocumentNotFound, DocumentTypes,
)
from woob.capabilities.bank.wealth import CapBankWealth
from woob.capabilities.contact import CapContact
from woob.capabilities.profile import CapProfile
from woob.tools.capabilities.bank.transactions import sorted_transactions
from woob.tools.backend import Module, BackendConfig
from woob.tools.value import Value, ValueBackendPassword, ValueTransient
from woob.capabilities.base import empty, find_object, NotAvailable, strict_find_object

from .browser import SocieteGenerale
from .sgpe.browser import SGEnterpriseBrowser, SGProfessionalBrowser


__all__ = ['SocieteGeneraleModule']


class SocieteGeneraleModule(
        Module, CapBankWealth, CapBankTransferAddRecipient, CapContact, CapProfile, CapDocument, CapBankMatching,
):
    NAME = 'societegenerale'
    MAINTAINER = u'Jocelyn Jaubert'
    EMAIL = 'jocelyn.jaubert@gmail.com'
    VERSION = '3.2'
    LICENSE = 'LGPLv3+'
    DESCRIPTION = u'Société Générale'
    CONFIG = BackendConfig(
        ValueBackendPassword('login', label='Code client', masked=False),
        ValueBackendPassword('password', label='Code secret'),
        Value(
            'website',
            label='Type de compte',
            default='par',
            choices={'par': 'Particuliers', 'pro': 'Professionnels', 'ent': 'Entreprises'}
        ),
        # SCA
        ValueTransient('code'),
        ValueTransient('resume'),
        ValueTransient('request_information'),
    )

    accepted_document_types = (DocumentTypes.STATEMENT, DocumentTypes.RIB)

    def create_default_browser(self):
        website = self.config['website'].get()
        browsers = {'par': SocieteGenerale, 'pro': SGProfessionalBrowser, 'ent': SGEnterpriseBrowser}
        self.BROWSER = browsers[website]

        return self.create_browser(
            self.config,
            self.config['login'].get(),
            self.config['password'].get()
        )

    def iter_accounts(self):
        for account in self.browser.get_accounts_list():
            yield account

    def get_account(self, _id):
        return find_object(self.browser.get_accounts_list(), id=_id, error=AccountNotFound)

    def fill_account(self, account, fields):
        if all((
            self.BROWSER == SocieteGenerale,
            'insurance_amount' in fields,
            account.type is Account.TYPE_LOAN,
        )):
            self.browser.fill_loan_insurance(account)

    def iter_coming(self, account):
        if hasattr(self.browser, 'get_cb_operations'):
            transactions = list(self.browser.get_cb_operations(account))
            return sorted_transactions(transactions)
        return self.browser.iter_coming(account)

    def iter_history(self, account):
        return self.browser.iter_history(account)

    def iter_investment(self, account):
        return self.browser.iter_investment(account)

    def iter_market_orders(self, account):
        return self.browser.iter_market_orders(account)

    def iter_contacts(self):
        if not hasattr(self.browser, 'get_advisor'):
            raise NotImplementedError()
        return self.browser.get_advisor()

    def get_profile(self):
        if not hasattr(self.browser, 'get_profile'):
            raise NotImplementedError()
        return self.browser.get_profile()

    def iter_transfer_recipients(self, origin_account, ignore_errors=True):
        if self.config['website'].get() not in ('par', 'pro'):
            raise NotImplementedError()
        if not isinstance(origin_account, Account):
            origin_account = find_object(self.iter_accounts(), id=origin_account, error=AccountNotFound)
        return self.browser.iter_recipients(origin_account, ignore_errors)

    def new_recipient(self, recipient, **params):
        if self.config['website'].get() not in ('par', 'pro'):
            raise NotImplementedError()
        recipient.label = ' '.join(w for w in re.sub(r'[^0-9a-zA-Z:\/\-\?\(\)\.,\'\+ ]+', '', recipient.label).split())
        return self.browser.new_recipient(recipient, **params)

    def init_transfer(self, transfer, **params):
        if self.config['website'].get() not in ('par', 'pro'):
            raise NotImplementedError()
        transfer.label = ' '.join(w for w in re.sub(r'[^0-9a-zA-Z ]+', '', transfer.label).split())
        self.logger.info('Going to do a new transfer')

        account = strict_find_object(self.iter_accounts(), iban=transfer.account_iban)
        if not account:
            account = strict_find_object(self.iter_accounts(), id=transfer.account_id, error=AccountNotFound)

        recipient = strict_find_object(
            self.iter_transfer_recipients(account.id, ignore_errors=False),
            id=transfer.recipient_id
        )
        if not recipient:
            recipient = strict_find_object(
                self.iter_transfer_recipients(account.id, ignore_errors=False),
                iban=transfer.recipient_iban,
                error=RecipientNotFound
            )

        transfer.amount = transfer.amount.quantize(Decimal('.01'))
        new_transfer = self.browser.init_transfer(account, recipient, transfer)

        # In some situations, we might get different account_id values for a
        # same account. A couple tests are run to ensure we do not raise
        # unwarranted errors.
        if transfer.account_id != new_transfer.account_id:
            # In this case, account_id might be the "identifiantPrestation"
            # which is like 'XXXXXXXXXXX<codeGuichet><numeroCompte>XXXXX'.
            # We only need to check this part of the account_id.
            if transfer.account_id[11:-5] != new_transfer.account_id:
                # account_id is still different from what we expected, but we
                # can ignore this if the account_iban is still the same.
                if transfer.account_iban != new_transfer.account_iban:
                    raise AssertionError('account_id changed during transfer processing (from "%s" to "%s").' % (
                        transfer.account_id,
                        new_transfer.account_id,
                    ))

        return new_transfer

    def execute_transfer(self, transfer, **params):
        if self.config['website'].get() not in ('par', 'pro'):
            raise NotImplementedError()
        return self.browser.execute_transfer(transfer)

    def transfer_check_label(self, old_label, new_label):
        old_label = unidecode(re.sub(r'\s+', ' ', old_label).strip())
        new_label = unidecode(re.sub(r'\s+', ' ', new_label).strip())

        if old_label == new_label:
            return True

        # societegenerale can add EMIS PAR at the end of the transfer label,
        # which causes a validation error. We want to remove it here,
        # to ensure later that the core of the label hasn't changed.
        #
        # We only want to remove the latest occurrence in the string, so that
        # "A - EMIS PAR ABC-DEF - EMIS PAR BCD-EFG" becomes
        # "A - EMIS PAR ABC-DEF" instead of simply "A", by using reversing
        # and lazy quantifier '.+?' instead of '.+'.
        new_label = re.sub(r'^.+?RAP SIME\s*-\s*', '', new_label[::-1])[::-1]
        return old_label == new_label

    def transfer_check_exec_date(self, old_exec_date, new_exec_date):
        return old_exec_date <= new_exec_date <= old_exec_date + timedelta(days=4)

    def transfer_check_account_id(self, old_account_id, new_account_id):
        # Checking account_id consistency is done in init_transfer.
        # This override is required to avoid the default check to happen.
        return True

    def transfer_check_recipient_id(self, old_recipient_id, new_recipient_id):
        if old_recipient_id == new_recipient_id:
            return True

        # In some cases (stet for example), the input recipient_id could be an iban
        # that will be matched with an account number formatted recipient id
        # In that case, the account number will be a part of the iban
        return empty(old_recipient_id) or new_recipient_id in old_recipient_id

    def iter_resources(self, objs, split_path):
        if Account in objs:
            self._restrict_level(split_path)
            return self.iter_accounts()
        if Subscription in objs:
            self._restrict_level(split_path)
            return self.iter_subscription()

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

    def iter_documents_by_types(self, subscription, accepted_types):
        if not isinstance(subscription, Subscription):
            subscription = self.get_subscription(subscription)

        if self.config['website'].get() not in ('ent', 'pro'):
            for doc in self.browser.iter_documents_by_types(subscription, accepted_types):
                yield doc
        else:
            for doc in self.browser.iter_documents(subscription):
                if doc.type in accepted_types:
                    yield doc

    def download_document(self, document):
        if not isinstance(document, Document):
            document = self.get_document(document)

        if document.url is NotAvailable:
            return

        return self.browser.open(document.url).content

    def iter_emitters(self):
        if self.config['website'].get() not in ('par', 'pro'):
            raise NotImplementedError()
        return self.browser.iter_emitters()

    def match_account(self, account, old_accounts):
        # If no match is found, and it's a card, try to match it by last 4 digits of
        # number.
        matched_accounts = []

        if account.type == Account.TYPE_CARD:
            for old_account in old_accounts:
                # the number can have two formats
                # 123456XXXXXX1234000
                # ************1234
                if (
                    old_account.type == Account.TYPE_CARD
                    and old_account.number
                    and old_account.number[:16][-4:] == account.number[:16][-4:]
                ):
                    matched_accounts.append(old_account)

        if len(matched_accounts) > 1:
            raise AssertionError(f'Found multiple candidates to match the card {account.label}.')

        if len(matched_accounts) == 1:
            return matched_accounts[0]

    OBJECTS = {
        Account: fill_account,
    }
