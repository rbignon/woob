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
from woob.capabilities.bank import Account
from woob.capabilities.bank.wealth import CapBankWealth
from woob.capabilities.base import find_object
from woob.capabilities.bill import CapDocument, Document, DocumentNotFound, DocumentTypes, Subscription
from woob.tools.backend import BackendConfig, Module
from woob.tools.value import Value, ValueBackendPassword, ValueTransient

from .proxy_browser import ProxyBrowser


__all__ = ['CaisseEpargneModule']


class CaisseEpargneModule(Module, CapBankWealth, CapDocument):
    NAME = 'caissedepargne'
    MAINTAINER = 'Romain Bignon'
    EMAIL = 'romain@weboob.org'
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

    accepted_document_types = (DocumentTypes.STATEMENT,)

    def create_default_browser(self):
        return self.create_browser(
            nuser=self.config['nuser'].get(),
            config=self.config,
            username=self.config['login'].get(),
            password=self.config['password'].get(),
        )

    def iter_resources(self, objs, split_path):
        if Account in objs:
            self._restrict_level(split_path)
            return self.iter_accounts()
        if Subscription in objs:
            self._restrict_level(split_path)
            return self.iter_subscription()

    # CapBank
    def iter_accounts(self):
        return self.browser.iter_accounts()

    def iter_history(self, account):
        return self.browser.iter_history(account)

    def iter_coming(self, account):
        return self.browser.iter_coming(account)

    # CapBankWealth
    def iter_investment(self, account):
        return self.browser.iter_investments(account)

    # CapDocument
    def iter_subscription(self):
        return self.browser.iter_subscriptions()

    def iter_documents(self, subscription):
        if not isinstance(subscription, Subscription):
            subscription = self.get_subscription(subscription)

        return self.browser.iter_documents(subscription)

    def get_document(self, _id):
        subid = _id.rsplit('_', 1)[0]
        subscription = self.get_subscription(subid)

        return find_object(self.iter_documents(subscription), id=_id, error=DocumentNotFound)

    def download_document(self, document):
        if not isinstance(document, Document):
            document = self.get_document(document)
        return self.browser.download_document(document)
