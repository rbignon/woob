# -*- coding: utf-8 -*-

# Copyright(C) 2010-2011 Julien Veyssier
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


import re
from decimal import Decimal

from woob.capabilities.base import find_object, NotAvailable
from woob.capabilities.bank import (
    CapBankTransferAddRecipient, AccountNotFound, RecipientNotFound,
    Account, TransferInvalidLabel,
)
from woob.capabilities.bank.pfm import CapBankMatching
from woob.capabilities.bank.wealth import CapBankWealth
from woob.capabilities.contact import CapContact
from woob.capabilities.profile import CapProfile
from woob.capabilities.bill import (
    CapDocument, Subscription, Document, DocumentNotFound, DocumentTypes,
)
from woob.tools.backend import Module, BackendConfig
from woob.tools.value import ValueBackendPassword, ValueTransient

from .browser import CreditMutuelBrowser


__all__ = ['CreditMutuelModule']


class CreditMutuelModule(
    Module, CapBankWealth, CapBankTransferAddRecipient, CapDocument,
    CapContact, CapProfile, CapBankMatching,
):

    NAME = 'creditmutuel'
    MAINTAINER = u'Julien Veyssier'
    EMAIL = 'julien.veyssier@aiur.fr'
    VERSION = '3.5'
    DESCRIPTION = u'Crédit Mutuel'
    LICENSE = 'LGPLv3+'
    CONFIG = BackendConfig(
        ValueBackendPassword('login', label='Identifiant', masked=False),
        ValueBackendPassword('password', label='Mot de passe'),
        ValueTransient('resume'),
        ValueTransient('request_information'),
        ValueTransient('code', regexp=r'^\d{6}$'),
    )
    BROWSER = CreditMutuelBrowser

    accepted_document_types = (DocumentTypes.STATEMENT, DocumentTypes.RIB)

    def create_default_browser(self):
        return self.create_browser(self.config, woob=self.woob)

    def iter_accounts(self):
        for account in self.browser.get_accounts_list():
            yield account

    def match_account(self, account, old_accounts):
        # This will work for most of accounts
        match = find_object(old_accounts, number=account.number, label=account.label)

        # But markets accounts can share a same ID for both accounts
        # So, if we do not have a match, we need to rely on the label
        if not match and (account.type == Account.TYPE_MARKET):
            for old_account in old_accounts:
                if old_account.label.lower() == account.label.lower():
                    match = old_account

        # If match is None, both find_object and relying on label failed
        # Which means it's a unknown account
        if match:
            self.logger.debug("Returning %s from matching_account", match)
        return match

    def get_account(self, _id):
        account = self.browser.get_account(_id)
        if account:
            return account
        else:
            raise AccountNotFound()

    def iter_coming(self, account):
        for tr in self.browser.get_history(account):
            if tr._is_coming:
                yield tr
            else:
                break

    def iter_history(self, account):
        for tr in self.browser.get_history(account):
            if not tr._is_coming:
                yield tr

    def iter_investment(self, account):
        return self.browser.get_investment(account)

    def iter_market_orders(self, account):
        return self.browser.iter_market_orders(account)

    def iter_transfer_recipients(self, origin_account):
        if not self.browser.is_new_website:
            self.logger.info('On old creditmutuel website')
            raise NotImplementedError()

        if not isinstance(origin_account, Account):
            origin_account = find_object(self.iter_accounts(), id=origin_account, error=AccountNotFound)
        return self.browser.iter_recipients(origin_account)

    def new_recipient(self, recipient, **params):
        # second step of the new_recipient
        # there should be a parameter
        if any(p in params for p in ('Bic', 'code', 'Clé', 'resume')):
            return self.browser.set_new_recipient(recipient, **params)

        return self.browser.new_recipient(recipient, **params)

    def init_transfer(self, transfer, **params):
        if {'Clé', 'resume', 'code'} & set(params.keys()):
            return self.browser.continue_transfer(transfer, **params)

        # There is a check on the website, transfer can't be done with too long reason.
        if transfer.label:
            transfer.label = transfer.label[:27]
            # Doing a full match with (?:<regex>)\Z, re.fullmatch works only
            # for python >=3.4.
            # re.UNICODE is needed to match letters with accents in python 2 only.
            regex = r"[-\w'/=:€?!.,() ]+"
            if not re.match(r"(?:%s)\Z" % regex, transfer.label, re.UNICODE):
                invalid_chars = re.sub(regex, '', transfer.label, flags=re.UNICODE)
                raise TransferInvalidLabel(
                    message="Le libellé de votre virement contient des caractères non autorisés : "
                    + invalid_chars
                )

        self.logger.info('Going to do a new transfer')

        account = None
        acc_list = list(self.iter_accounts())
        if transfer.account_iban:
            account = find_object(acc_list, iban=transfer.account_iban)
        if not account:
            account = find_object(acc_list, id=transfer.account_id, error=AccountNotFound)

        recipient = None
        rcpt_list = list(self.iter_transfer_recipients(account.id))
        if transfer.recipient_iban:
            recipient = find_object(rcpt_list, iban=transfer.recipient_iban)
        if not recipient:
            recipient = find_object(rcpt_list, id=transfer.recipient_id, error=RecipientNotFound)

        assert account.id.isdigit(), 'Account id is invalid'

        # quantize to show 2 decimals.
        transfer.amount = Decimal(transfer.amount).quantize(Decimal(10) ** -2)

        # drop characters that can crash website
        transfer.label = transfer.label.encode('cp1252', errors="ignore").decode('cp1252')

        return self.browser.init_transfer(transfer, account, recipient)

    def execute_transfer(self, transfer, **params):
        return self.browser.execute_transfer(transfer)

    def iter_contacts(self):
        return self.browser.get_advisor()

    def get_profile(self):
        if not hasattr(self.browser, 'get_profile'):
            raise NotImplementedError()
        return self.browser.get_profile()

    def get_document(self, _id):
        subscription_id = _id.split('_')[0]
        subscription = self.get_subscription(subscription_id)
        return find_object(self.iter_documents(subscription), id=_id, error=DocumentNotFound)

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

        return self.browser.open(document.url).content

    def iter_resources(self, objs, split_path):
        if Account in objs:
            self._restrict_level(split_path)
            return self.iter_accounts()
        if Subscription in objs:
            self._restrict_level(split_path)
            return self.iter_subscription()

    def iter_emitters(self):
        return self.browser.iter_emitters()
