# -*- coding: utf-8 -*-

# Copyright(C) 2019      Vincent A
#
# This file is part of a weboob module.
#
# This weboob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This weboob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this weboob module. If not, see <http://www.gnu.org/licenses/>.

# flake8: compatible

from __future__ import unicode_literals

from weboob.tools.backend import Module, BackendConfig
from weboob.tools.value import Value, ValueBackendPassword
from weboob.capabilities.base import find_object
from weboob.capabilities.bank import CapBank, Account
from weboob.capabilities.bill import (
    CapDocument, Subscription, SubscriptionNotFound, DocumentNotFound,
)

from .browser import PrimonialreimBrowser


__all__ = ['PrimonialreimModule']


class PrimonialreimModule(Module, CapBank, CapDocument):
    NAME = 'primonialreim'
    DESCRIPTION = 'Primonial REIM'
    MAINTAINER = 'Vincent A'
    EMAIL = 'dev@indigo.re'
    LICENSE = 'LGPLv3+'
    VERSION = '3.1'

    BROWSER = PrimonialreimBrowser

    CONFIG = BackendConfig(
        Value('username', label='Identifiant'),
        ValueBackendPassword('password', label='Mot de passe'),
    )

    def create_default_browser(self):
        return self.create_browser(self.config['username'].get(), self.config['password'].get())

    # CapBank
    def iter_accounts(self):
        return self.browser.iter_accounts()

    # CapDocument
    def iter_subscription(self):
        return [Subscription.from_dict(dict(id="primonial", label="Primonial"))]

    def get_subscription(self, id):
        return find_object(self.iter_subscription(), id=id, error=SubscriptionNotFound)

    def iter_documents(self, subscription):
        return self.browser.iter_documents()

    def get_document(self, id):
        return find_object(self.iter_documents(None), id=id, error=DocumentNotFound)

    def download_document(self, document):
        if isinstance(document, str):
            document = find_object(self.iter_documents(None), id=document, error=DocumentNotFound)
        return self.browser.open(document.url).content

    # CapCollection
    def iter_resources(self, objs, split_path):
        if Account in objs:
            self._restrict_level(split_path)
            return self.iter_accounts()
        if Subscription in objs:
            self._restrict_level(split_path)
            return self.iter_subscription()
