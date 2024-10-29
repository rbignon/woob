# -*- coding: utf-8 -*-

# Copyright(C) 2010-2013  Romain Bignon, Pierre Mazière
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

from woob.capabilities.bank import Account
from woob.capabilities.bank.pfm import CapBankMatching
from woob.capabilities.bank.wealth import CapBankWealth
from woob.capabilities.base import empty, find_object
from woob.capabilities.bill import (
    CapDocument, Subscription, SubscriptionNotFound,
    Document, DocumentNotFound, DocumentTypes,
)
from woob.exceptions import implemented_websites
from woob.tools.backend import Module, BackendConfig
from woob.tools.value import Value, ValueBackendPassword, ValueTransient

from .browser import LCLBrowser
from .enterprise.browser import LCLEnterpriseBrowser, LCLEspaceProBrowser
from .proxy_browser import ProxyBrowser


__all__ = ['LCLModule']


class LCLModule(Module, CapBankWealth, CapBankMatching, CapDocument):
    NAME = 'lcl'
    MAINTAINER = u'Romain Bignon'
    EMAIL = 'romain@weboob.org'
    VERSION = '3.7'
    DESCRIPTION = u'LCL'
    LICENSE = 'LGPLv3+'
    CONFIG = BackendConfig(
        ValueBackendPassword('login', label='Identifiant', masked=False),
        ValueBackendPassword('password', label='Code personnel'),
        Value(
            'website',
            label='Type de compte',
            default='par',
            choices={
                'par': 'Particuliers',
                'pro': 'Professionnels',
                'ent': 'Entreprises',
                'esp': 'Espace Pro',
            },
            aliases={'elcl': 'par'}
        ),
        ValueTransient('resume'),
        ValueTransient('request_information'),
        ValueTransient('code', regexp=r'^\d{6}$'),
    )
    BROWSER = LCLBrowser

    accepted_document_types = (DocumentTypes.STATEMENT,)

    def create_default_browser(self):
        browsers = {
            'par': LCLBrowser,
            'pro': LCLBrowser,
            'ent': LCLEnterpriseBrowser,
            'esp': LCLEspaceProBrowser,
            'cards': ProxyBrowser,
        }

        website_value = self.config['website']
        self.BROWSER = browsers.get(
            website_value.get(),
            browsers[website_value.default]
        )

        return self.create_browser(
            self.config,
            self.config['login'].get(),
            self.config['password'].get()
        )

    def iter_accounts(self):
        return self.browser.iter_accounts()

    def iter_coming(self, account):
        return self.browser.iter_coming(account)

    def iter_history(self, account):
        return self.browser.iter_history(account)

    def iter_investment(self, account):
        return self.browser.iter_investment(account)

    def match_account(self, account, previous_accounts):
        # Ids of cards are not consistent with other LCL sources.
        # Try matching on card number and coming amount.

        if account.type != Account.TYPE_CARD:
            return None

        matched_accounts = []
        for previous_account in previous_accounts:

            if (
                previous_account.type == Account.TYPE_CARD
                and previous_account.number == account.number
                and previous_account.coming == account.coming
            ):
                matched_accounts.append(previous_account)

            # to match accounts between old and new websites
            elif (
                previous_account.type == Account.TYPE_CARD
                and account.number[0] == '_'
                and previous_account.number[:3] == account.number[:3]
            ):
                matched_accounts.append(previous_account)

        if len(matched_accounts) > 1:
            raise AssertionError(f'Found multiple candidates to match the card {account.label}.')

        if matched_accounts:
            self.logger.info(
                "Matched new account '%s' with previous account '%s' from matching_account",
                account,
                matched_accounts[0]
            )
            return matched_accounts[0]

        # explicit return if no match found
        return None

    @implemented_websites('par', 'elcl', 'pro')
    def iter_subscription(self):
        return self.browser.iter_subscriptions()

    @implemented_websites('par', 'elcl', 'pro')
    def get_subscription(self, _id):
        return find_object(self.iter_subscription(), id=_id, error=SubscriptionNotFound)

    @implemented_websites('par', 'elcl', 'pro')
    def iter_documents(self, subscription):
        if not isinstance(subscription, Subscription):
            subscription = self.get_subscription(subscription)

        return self.browser.iter_documents(subscription)

    @implemented_websites('par', 'elcl', 'pro')
    def get_document(self, _id):
        subscription_id = _id.split("_")[0]
        subscription = self.get_subscription(subscription_id)
        return find_object(
            self.iter_documents(subscription), id=_id, error=DocumentNotFound
        )

    @implemented_websites('par', 'elcl', 'pro')
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
