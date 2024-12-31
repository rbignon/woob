# -*- coding: utf-8 -*-

# Copyright(C) 2016      Edouard Lambert
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


from woob.capabilities.base import NotAvailable, find_object
from woob.capabilities.bill import (
    CapDocument, Document, DocumentCategory, DocumentNotFound, DocumentTypes, Subscription,
)
from woob.tools.backend import BackendConfig, Module
from woob.tools.value import ValueBackendPassword

from .browser import TrainlineBrowser


__all__ = ['TrainlineModule']


class TrainlineModule(Module, CapDocument):
    NAME = 'trainline'
    DESCRIPTION = 'trainline'
    MAINTAINER = 'Edouard Lambert'
    EMAIL = 'elambert@budget-insight.com'
    LICENSE = 'LGPLv3+'
    VERSION = '3.7'
    CONFIG = BackendConfig(
        ValueBackendPassword('login', label='Adresse email'),
        ValueBackendPassword('password', label='Mot de passe')
    )

    BROWSER = TrainlineBrowser

    accepted_document_types = (DocumentTypes.BILL,)
    document_categories = {DocumentCategory.TRANSPORT}

    def create_default_browser(self):
        return self.create_browser(self.config['login'].get(), self.config['password'].get())

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
