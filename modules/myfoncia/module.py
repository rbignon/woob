# -*- coding: utf-8 -*-

# Copyright(C) 2017      Phyks (Lucas Verney)
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


from woob.tools.backend import Module, BackendConfig
from woob.capabilities.base import find_object
from woob.capabilities.bill import (
    CapDocument, DocumentNotFound,
    Subscription, DocumentTypes, Document,
)
from woob.tools.value import ValueBackendPassword

from .browser import MyFonciaBrowser


__all__ = ['MyFonciaModule']


class MyFonciaModule(Module, CapDocument):
    NAME = 'myfoncia'
    DESCRIPTION = u'Foncia billing capabilities'
    MAINTAINER = u'Phyks (Lucas Verney)'
    EMAIL = 'phyks@phyks.me'
    LICENSE = 'LGPLv3+'
    VERSION = '3.0'
    CONFIG = BackendConfig(
        ValueBackendPassword('login', label='Email address or Foncia ID'),
        ValueBackendPassword('password', label='Password'),
    )
    BROWSER = MyFonciaBrowser

    accepted_document_types = (DocumentTypes.BILL, DocumentTypes.REPORT,)

    def create_default_browser(self):
        return self.create_browser(
            self.config['login'].get(),
            self.config['password'].get()
        )

    def iter_subscription(self):
        return self.browser.get_subscriptions()

    def iter_documents(self, subscription):
        if isinstance(subscription, Subscription):
            subscription_id = subscription.id
        else:
            subscription_id = subscription
        return self.browser.get_documents(subscription_id)

    def get_document(self, _id):
        subid = _id.rsplit('_', 1)[0]
        subscription = self.get_subscription(subid)

        return find_object(self.iter_documents(subscription), id=_id, error=DocumentNotFound)

    def download_document(self, document):
        if not isinstance(document, Document):
            document = self.get_document(document)

        if not document.url:
            return None

        return self.browser.open(document.url).content
