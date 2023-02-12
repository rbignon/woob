# flake8: compatible

# Copyright(C) 2022 Thomas Touhey <thomas@touhey.fr>
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

from woob.capabilities.base import find_object
from woob.capabilities.bill import (
    CapDocument, Document, DocumentCategory, DocumentNotFound, Subscription,
)
from woob.capabilities.profile import CapProfile
from woob.tools.backend import BackendConfig, Module
from woob.tools.value import Value, ValueBackendPassword

from .gercop import GercopBrowser

__all__ = ['LAdresseModule']


class LAdresseModule(Module, CapDocument, CapProfile):
    NAME = 'ladresse'
    DESCRIPTION = "L'Adresse"
    MAINTAINER = 'Thomas Touhey'
    EMAIL = 'thomas@touhey.fr'
    LICENSE = 'LGPLv3+'
    VERSION = '3.3.1'

    # All L'Adresse agencies are franchisees who choose the platform
    # on which they wish to make documents available to their tenants
    # and owners.
    #
    # NOTE: Your agency's website isn't here? You can add it here, and
    #       add the browser if it doesn't already exist in a submodule,
    #       like for Gercop.
    WEBSITES = {
        'ladresse-bsgestion.gercop-extranet.com': GercopBrowser,
        'adresseavenir.gercop-extranet.com': GercopBrowser,
        'ladresse-valerie-immobilier.mygercop.com': GercopBrowser,
        'ladresse.logique-extranet.com': GercopBrowser,
        'gambettaimmobilier.logique-extranet.com': GercopBrowser,
        'cersoyetgirard.logique-extranet.com': GercopBrowser,
    }

    CONFIG = BackendConfig(
        ValueBackendPassword(
            'login',
            label='Identifiant',
            regexp=r'[A-Z]\d{6}',
            required=True,
            masked=False,
        ),
        ValueBackendPassword(
            'password',
            label='Mot de passe',
            required=True,
        ),
        Value(
            'website',
            label='Extranet',
            choices={key: key for key in WEBSITES.keys()},
            required=True,
        ),
    )

    document_categories = {DocumentCategory.REAL_ESTATE, }

    def create_default_browser(self):
        website = self.config['website'].get()
        return self.create_browser(
            f'https://{website}/',
            self.config['login'].get(),
            self.config['password'].get(),
            klass=self.WEBSITES[website],
        )

    def iter_subscription(self):
        profile = self.get_profile()

        subscription = Subscription()
        subscription.id = 'ladresse'
        subscription.label = profile.name
        yield subscription

    def iter_documents(self, subscription):
        return self.browser.iter_documents()

    def get_document(self, id):
        return find_object(
            self.browser.iter_documents(),
            id=id,
            error=DocumentNotFound,
        )

    def download_document(self, document):
        if not isinstance(document, Document):
            document = self.get_document(document)

        return self.browser.download_document(document)

    def get_profile(self):
        return self.browser.get_profile()
