# Copyright(C) 2019 Powens
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
    CapDocument, Document, DocumentCategory, DocumentNotFound, DocumentTypes, Subscription,
)
from woob.capabilities.profile import CapProfile
from woob.tools.backend import Module, BackendConfig
from woob.tools.value import ValueBackendPassword, ValueTransient

from .browser import AmeliBrowser

__all__ = ['AmeliModule']


class AmeliModule(Module, CapDocument, CapProfile):
    NAME = 'ameli'
    DESCRIPTION = "le site de l'Assurance Maladie en ligne"
    MAINTAINER = 'Florian Duguet'
    EMAIL = 'florian.duguet@budget-insight.com'
    LICENSE = 'LGPLv3+'
    VERSION = '3.6'
    DEPENDENCIES = ('franceconnect',)

    BROWSER = AmeliBrowser

    CONFIG = BackendConfig(
        ValueBackendPassword('login', label="Identifiant (dépend de votre méthode d'authentification)", masked=False),
        ValueBackendPassword('password', label='Mot de passe'),
        ValueTransient('request_information'),
        ValueTransient('otp_email', regexp=r'\d{6}'),
        ValueTransient('login_source', default='direct'),  # for backward compatibility purpose
    )

    accepted_document_types = (DocumentTypes.BILL,)
    document_categories = {DocumentCategory.ADMINISTRATIVE}

    def create_default_browser(self):
        return self.create_browser(
            self.config,
            self.config['login'].get(),
            self.config['password'].get()
        )

    def iter_subscription(self):
        return self.browser.iter_subscription()

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

        return self.browser.open(document.url).content

    def get_profile(self):
        return self.browser.get_profile()
