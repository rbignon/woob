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

from woob.capabilities.base import find_object
from woob.capabilities.bill import (
    CapDocument, DocumentCategory, DocumentTypes, DocumentNotFound,
)
from woob.tools.backend import BackendConfig, Module
from woob.tools.value import ValueBackendPassword

from .browser import EnsapBrowser

__all__ = ['EnsapModule']


class EnsapModule(Module, CapDocument):
    NAME = 'ensap'
    DESCRIPTION = u'ENSAP'
    MAINTAINER = u'Juliette Fourcot'
    EMAIL = 'juliette@fourcot.fr'
    LICENSE = 'LGPLv3+'
    VERSION = '3.4'

    BROWSER = EnsapBrowser
    CONFIG = BackendConfig(
        ValueBackendPassword('login', label='Identifiant', regexp=r'[0-9]{15}', masked=False),
        ValueBackendPassword('password', label='Mot de passe'),
    )
    accepted_document_types = (DocumentTypes.PAYSLIP,)
    document_categories = {DocumentCategory.SAFE_DEPOSIT_BOX}

    def create_default_browser(self):
        return self.create_browser(
            self.config['login'].get(), self.config['password'].get()
        )

    def iter_subscription(self):
        return self.browser.iter_subscription()

    def iter_documents(self, subscription):
        return self.browser.iter_documents()

    def get_document(self, id):
        return find_object(self.browser.iter_documents(), id=id, error=DocumentNotFound)

    def download_document(self, doc):
        return self.browser.open(doc.url).content
