# Copyright(C) 2019      Budget Insight
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
from woob.tools.backend import BackendConfig
from woob.capabilities.bill import (
    CapDocument, Document, DocumentNotFound, DocumentTypes,
    Subscription, SubscriptionNotFound,
)
from woob.tools.value import ValueBackendPassword, Value
from woob_modules.franceconnect.module import FranceConnectModule

from .browser import AmeliBrowser

__all__ = ['AmeliModule']


class AmeliModule(FranceConnectModule, CapDocument):
    NAME = 'ameli'
    DESCRIPTION = "le site de l'Assurance Maladie en ligne"
    MAINTAINER = 'Florian Duguet'
    EMAIL = 'florian.duguet@budget-insight.com'
    LICENSE = 'LGPLv3+'
    VERSION = '3.1'

    BROWSER = AmeliBrowser

    CONFIG = BackendConfig(
        ValueBackendPassword('login', label="Identifiant (dépend de votre méthode d'authentification)", masked=False),
        ValueBackendPassword('password', label='Mot de passe'),
        Value(
            'login_source', label="Méthode d'authentification", default='direct',
            choices={
                'direct': 'Directe',
                'fc_ameli': 'France Connect Ameli',
                'fc_impots': 'France Connect Impôts',
            }
        ),
    )

    accepted_document_types = (DocumentTypes.BILL,)

    def create_default_browser(self):
        return self.create_browser(self.config)

    def iter_subscription(self):
        return self.browser.iter_subscription()

    def get_subscription(self, _id):
        return find_object(self.iter_subscription(), id=_id, error=SubscriptionNotFound)

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
