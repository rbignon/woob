# -*- coding: utf-8 -*-

# Copyright(C) 2017      P4ncake
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


from woob.capabilities.bill import (
    DocumentCategory, DocumentTypes, CapDocument, Subscription, Document, DocumentNotFound,
)
from woob.capabilities.base import find_object, NotAvailable
from woob.tools.backend import Module, BackendConfig
from woob.tools.value import ValueBackendPassword, ValueTransient

from .browser import CityscootBrowser


__all__ = ['CityscootModule']


class CityscootModule(Module, CapDocument):
    NAME = 'cityscoot'
    DESCRIPTION = 'Le scooter électrique en libre-service, sans bornes.'
    MAINTAINER = 'P4ncake'
    EMAIL = 'me@p4ncake.fr'
    LICENSE = 'LGPLv3+'
    VERSION = '3.5'
    CONFIG = BackendConfig(
        ValueBackendPassword('login', label='Adresse email', masked=False),
        ValueBackendPassword('password', label='Mot de passe'),
        ValueTransient('captcha_response', label='Captcha Response')
    )

    BROWSER = CityscootBrowser

    accepted_document_types = (DocumentTypes.BILL,)
    document_categories = {DocumentCategory.TRANSPORT}

    def create_default_browser(self):
        return self.create_browser(self.config)

    def iter_subscription(self):
        return self.browser.get_subscription_list()

    def get_document(self, _id):
        subid = _id.rsplit('_', 1)[0]
        subscription = self.get_subscription(subid)

        return find_object(self.iter_documents(subscription), id=_id, error=DocumentNotFound)

    def iter_documents(self, subscription):
        if not isinstance(subscription, Subscription):
            subscription = self.get_subscription(subscription)
        return self.browser.iter_documents(subscription)

    def download_document(self, document):
        if not isinstance(document, Document):
            document = self.get_document(document)
        if document.url is NotAvailable:
            return

        return self.browser.open(document.url).content
