# Copyright(C) 2022-2023 Powens
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

from woob.capabilities.bank.wealth import CapBankWealth
from woob.capabilities.base import find_object
from woob.capabilities.bill import CapDocument, Document, DocumentNotFound, DocumentTypes
from woob.capabilities.profile import CapProfile
from woob.tools.backend import Module, BackendConfig
from woob.tools.value import ValueBackendPassword

from .browser import MilleisBrowser


__all__ = ['MilleisModule']


class MilleisModule(Module, CapBankWealth, CapProfile, CapDocument):
    NAME = 'milleis'
    MAINTAINER = 'Jean Walrave'
    EMAIL = 'jwalrave@budget-insight.com'
    VERSION = "3.7"
    DESCRIPTION = 'Milleis'
    LICENSE = 'LGPLv3+'
    CONFIG = BackendConfig(
        ValueBackendPassword('login', label="N° d'abonné", masked=False),
        ValueBackendPassword('password', label='Code confidentiel', regexp=r'\d+'),
    )
    BROWSER = MilleisBrowser

    accepted_document_types = (DocumentTypes.STATEMENT,)

    def create_default_browser(self):
        return self.create_browser(
            self.config['login'].get(),
            self.config['password'].get(),
        )

    def iter_accounts(self):
        return self.browser.iter_accounts()

    def iter_history(self, account):
        return self.browser.iter_history(account)

    def iter_investment(self, account):
        return self.browser.iter_investments(account)

    def get_profile(self):
        return self.browser.get_profile()

    def iter_subscription(self):
        return self.browser.iter_subscriptions()

    def iter_documents(self, subscription):
        return self.browser.iter_documents(subscription)

    def get_document(self, _id):
        subid = _id.rsplit('_', 1)[0]
        subscription = self.get_subscription(subid)

        return find_object(self.iter_documents(subscription), id=_id, error=DocumentNotFound)

    def download_document(self, document):
        if not isinstance(document, Document):
            document = self.get_document(document)
        return self.browser.download_document(document)
