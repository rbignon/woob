# -*- coding: utf-8 -*-

# Copyright(C) 2012-2020  Budget Insight
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

from __future__ import unicode_literals


from woob.capabilities.bill import (
    DocumentTypes, CapDocument, Subscription, Document, DocumentNotFound,
    DocumentCategory,
)
from woob.capabilities.base import find_object
from woob.tools.backend import Module, BackendConfig
from woob.tools.value import ValueBackendPassword, Value, ValueTransient
from woob.capabilities.profile import CapProfile

from .browser import EdfParticulierBrowser


__all__ = ['EdfparticulierModule']


class EdfparticulierModule(Module, CapDocument, CapProfile):
    NAME = 'edfparticulier'
    DESCRIPTION = 'edf particulier'
    MAINTAINER = 'Florian Duguet'
    EMAIL = 'florian.duguet@budget-insight.com'
    LICENSE = 'LGPLv3+'
    VERSION = '3.2'

    BROWSER = EdfParticulierBrowser

    CONFIG = BackendConfig(
        Value('login', label='E-mail ou Identifiant'),
        ValueBackendPassword('password', label='Mot de passe'),
        ValueTransient('otp', label='Entrez le code reçu par SMS'),
        ValueTransient('request_information'),
    )

    accepted_document_types = (DocumentTypes.BILL,)
    document_categories = {DocumentCategory.ENERGY}

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
        return self.browser.download_document(document)

    def get_profile(self):
        return self.browser.get_profile()
