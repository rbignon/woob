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

from woob.capabilities.base import find_object
from woob.capabilities.bill import (
    CapDocument, Document, DocumentNotFound, DocumentTypes, DocumentCategory,
)
from woob.capabilities.profile import CapProfile
from woob.tools.backend import BackendConfig, Module
from woob.tools.value import ValueBackendPassword, ValueTransient

from .browser import NRJMobileBrowser

__all__ = ['NRJMobileModule']


class NRJMobileModule(Module, CapDocument, CapProfile):
    NAME = 'nrjmobile'
    DESCRIPTION = 'NRJ Mobile'
    MAINTAINER = 'Powens'
    EMAIL = 'dev@powens.com'
    LICENSE = 'LGPLv3+'
    VERSION = '3.7'

    CONFIG = BackendConfig(
        ValueBackendPassword('login', label='Identifiant', masked=False),
        ValueBackendPassword('password', label='Code confidentiel'),
        ValueTransient('captcha_response'),
    )

    BROWSER = NRJMobileBrowser

    accepted_document_types = (DocumentTypes.BILL,)
    document_categories = {DocumentCategory.INTERNET_TELEPHONY}

    def create_default_browser(self):
        return self.create_browser(self.config)

    def iter_subscription(self):
        # NOTE: This module has been developed against an account with a
        #       single subscription.
        #
        #       It might be possible for an account to have multiple
        #       subscriptions, based on what can be found in
        #       "Votre compte > Gestion de vos groupes de lignes".
        yield self.browser.get_subscription()

    def iter_documents(self, subscription):
        # NOTE: This function returns all documents for 'all' subscriptions,
        #       since there is only one subscription in test cases.
        return self.browser.iter_documents()

    def get_document(self, id_):
        return find_object(
            self.browser.iter_documents(),
            id=id_,
            error=DocumentNotFound,
        )

    def download_document(self, document):
        if not isinstance(document, Document):
            document = self.get_document(document)

        return self.browser.download_document(document)

    def get_profile(self):
        return self.browser.get_profile()
