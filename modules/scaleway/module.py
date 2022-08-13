# -*- coding: utf-8 -*-

# Copyright(C) 2022      Jeremy Demange (scrapfast.io)
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

from __future__ import unicode_literals


from woob.capabilities.bill import (
    DocumentCategory, DocumentTypes, CapDocument,
    Document, DocumentNotFound, Subscription
)
from woob.capabilities.base import find_object, NotAvailable
from woob.tools.backend import Module, BackendConfig
from woob.tools.value import ValueBackendPassword, ValueTransient

from woob.capabilities.profile import CapProfile
from woob.capabilities.account import CapAccount

from .browser import ScalewayBrowser


__all__ = ['ScalewayModule']


class ScalewayModule(Module, CapDocument, CapProfile, CapAccount):
    NAME = 'scaleway'
    DESCRIPTION = 'Scaleway'
    MAINTAINER = 'Jeremy Demange'
    EMAIL = 'jeremy@scrapfast.io'
    LICENSE = 'LGPLv3+'
    VERSION = '3.1'
    CONFIG = BackendConfig(
        ValueBackendPassword('login', label='Email de connexion', masked=False),
        ValueBackendPassword('password', label='Mot de passe'),
        ValueTransient('otp'),
    )

    BROWSER = ScalewayBrowser

    accepted_document_types = (DocumentTypes.BILL, DocumentTypes.OTHER,)
    document_categories = {DocumentCategory.SOFTWARE}

    def create_default_browser(self):
        return self.create_browser(self.config)

    def get_profile(self):
        return self.browser.get_profile()

    def iter_subscription(self):
        return self.browser.get_subscription_list()

    def get_document(self, _id):
        return find_object(self.iter_documents(), id=_id, error=DocumentNotFound)

    def iter_documents(self, subscription=''):
        if isinstance(subscription, Subscription):
            subscription = subscription.id
        return self.browser.iter_documents(subscription)

    def download_document(self, document):
        if not isinstance(document, Document):
            document = self.get_document(document)
        if document.url is NotAvailable:
            return
        return self.browser.download_document(document)
