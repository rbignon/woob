# Copyright(C) 2012      Gabriel Serme
# Copyright(C) 2011      Gabriel Kerneis
# Copyright(C) 2010-2011 Jocelyn Jaubert
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

from woob.capabilities.bank import Account, CapBankTransferAddRecipient, CapBankWealth, CapCurrencyRate
from woob.capabilities.bank.pfm import CapBankMatching
from woob.capabilities.base import empty, find_object
from woob.capabilities.bill import CapDocument, Document, DocumentNotFound, DocumentTypes, Subscription
from woob.capabilities.contact import CapContact
from woob.capabilities.profile import CapProfile
from woob.tools.backend import BackendConfig, Module
from woob.tools.value import Value, ValueBackendPassword, ValueTransient

from .browser import BoursoramaBrowser


__all__ = ["BoursoramaModule"]


class BoursoramaModule(
    Module,
    CapBankWealth,
    CapBankTransferAddRecipient,
    CapProfile,
    CapContact,
    CapCurrencyRate,
    CapDocument,
    CapBankMatching,
):
    NAME = "boursorama"
    MAINTAINER = "Gabriel Kerneis"
    EMAIL = "gabriel@kerneis.info"
    LICENSE = "LGPLv3+"
    DESCRIPTION = "Boursorama"
    CONFIG = BackendConfig(
        ValueBackendPassword("login", label="Identifiant", masked=False, regexp=r"^[0-9]+$"),
        ValueBackendPassword("password", label="Mot de passe", regexp=r"[a-zA-Z0-9]+"),
        Value("identity", label="ID d'identité", required=False),
        ValueTransient("code"),
        ValueTransient("email_code"),
        ValueTransient("resume"),
        ValueTransient("request_information"),
    )

    BROWSER = BoursoramaBrowser

    accepted_document_types = (DocumentTypes.STATEMENT, DocumentTypes.RIB)

    def create_default_browser(self):
        return self.create_browser(self.config)

    def iter_accounts(self):
        return self.browser.get_accounts_list()

    def iter_history(self, account):
        for tr in self.browser.get_history(account):
            if not tr.coming:
                yield tr

    def iter_coming(self, account):
        for tr in self.browser.get_history(account, coming=True):
            if tr.coming:
                yield tr

    def iter_investment(self, account):
        return self.browser.iter_investment(account)

    def iter_market_orders(self, account):
        return self.browser.iter_market_orders(account)

    def get_profile(self):
        return self.browser.get_profile()

    def iter_contacts(self):
        return self.browser.get_advisor()

    def iter_transfer_recipients(self, account):
        if not isinstance(account, Account):
            account = self.get_account(account)
        return self.browser.iter_transfer_recipients(account)

    def init_transfer(self, transfer, **kwargs):
        # Continue a previously initiated transfer if an otp info is given (ie otp_sms, otp_email)
        if self.browser.otp_validation_continue_transfer(transfer, **kwargs):
            # The otp step is performed on the confirmation page.
            # so, from there, we should continue processing at execute_transfer subsequently
            return transfer
        return self.browser.init_transfer(transfer, **kwargs)

    def new_recipient(self, recipient, **kwargs):
        return self.browser.new_recipient(recipient, **kwargs)

    def execute_transfer(self, transfer, **kwargs):
        return self.browser.execute_transfer(transfer, **kwargs)

    def iter_transfers(self, account):
        return self.browser.iter_transfers(account)

    def get_transfer(self, id):
        # we build the id of the transfer by prefixing the account id (in pages.py)
        # precisely for this use case, because we want to only query on the right account
        account_id, _, transfer_id = id.partition(".")
        return find_object(self.browser.iter_transfers_for_account(account_id), id=id)

    def transfer_check_label(self, old, new):
        # In the confirm page the '<' is interpeted like a html tag
        # If no '>' is present the following chars are deleted
        # Else: inside '<>' chars are deleted
        old = re.sub(r"<[^>]*>", "", old).strip()
        old = old.split("<")[0]

        # replace � by ?, like the bank does
        old = old.replace("\ufffd", "?")
        return super().transfer_check_label(old, new)

    def transfer_check_account_id(self, old, new):
        # We can't verify here automatically that the account_id has not changed
        # as it might have changed early if a stet account id was provided
        # instead of the account id that we use here coming from the website.
        # And in addition, we don't get the account id from the confirmation page
        # to perform such a check anyway.
        return True

    def iter_currencies(self):
        return self.browser.iter_currencies()

    def get_rate(self, currency_from, currency_to):
        return self.browser.get_rate(currency_from, currency_to)

    def iter_emitters(self):
        return self.browser.iter_emitters()

    def fill_account(self, account, fields):
        if (
            "opening_date" in fields
            and account.type == Account.TYPE_LIFE_INSURANCE
            and "/compte/derive" not in account.url
        ):
            account.opening_date = self.browser.get_opening_date(account.url)

    def get_document(self, _id):
        subscription_id = _id.split("_")[0]
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
        if empty(document.url):
            return

        return self.browser.open(document.url).content

    def iter_resources(self, objs, split_path):
        if Account in objs:
            self._restrict_level(split_path)
            return self.iter_accounts()
        if Subscription in objs:
            self._restrict_level(split_path)
            return self.iter_subscription()

    def match_account(self, account, old_accounts):
        matched_accounts = []

        if account.type == Account.TYPE_CARD:
            for old_account in old_accounts:
                if old_account.type == Account.TYPE_CARD and old_account.number == account.number:
                    matched_accounts.append(old_account)

        if len(matched_accounts) > 1:
            raise AssertionError(f"Found multiple candidates to match the card {account.label}.")

        if len(matched_accounts) == 1:
            return matched_accounts[0]

    OBJECTS = {
        Account: fill_account,
    }
