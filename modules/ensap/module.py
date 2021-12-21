# -*- coding: utf-8 -*-

# Copyright(C) 2017      Juliette Fourcot
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

from woob.capabilities.base import find_object
from woob.capabilities.bill import CapDocument, SubscriptionNotFound, DocumentTypes
from woob.tools.backend import BackendConfig, Module
from woob.tools.value import ValueBackendPassword

from .browser import EnsapBrowser

__all__ = ['EnsapModule']


class EnsapModule(Module, CapDocument):
    NAME = 'ensap'
    DESCRIPTION = u'ensap website'
    MAINTAINER = u'Juliette Fourcot'
    EMAIL = 'juliette@fourcot.fr'
    LICENSE = 'LGPLv3+'
    VERSION = '3.1'

    BROWSER = EnsapBrowser
    CONFIG = BackendConfig(
        ValueBackendPassword('login', label='Identifiant', regexp=r'[0-9]{15}', masked=False),
        ValueBackendPassword('password', label='Mot de passe'),
    )
    accepted_document_types = (DocumentTypes.OTHER,)

    def create_default_browser(self):
        return self.create_browser(
            self.config['login'].get(), self.config['password'].get()
        )

    def get_document(self, _id):
        return self.browser.get_document(_id)

    def get_subscription(self, _id):
        return find_object(
            self.browser.iter_subscription(), id=_id, error=SubscriptionNotFound
        )

    def iter_documents(self, subscription):
        return self.browser.iter_documents(subscription)

    def iter_subscription(self):
        return self.browser.iter_subscription()

    def download_document(self, doc):
        return self.browser.open(doc.url).content
