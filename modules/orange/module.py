# -*- coding: utf-8 -*-

# Copyright(C) 2010-2011 Nicolas Duhamel
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

from woob.capabilities.bill import DocumentTypes, CapDocument, Subscription, Document, SubscriptionNotFound, DocumentNotFound
from woob.capabilities.base import find_object, NotAvailable
from woob.capabilities.account import CapAccount
from woob.capabilities.profile import CapProfile
from woob.tools.backend import Module, BackendConfig
from woob.tools.value import ValueBackendPassword

from .browser import OrangeBillBrowser


__all__ = ['OrangeModule']


class OrangeModule(Module, CapAccount, CapDocument, CapProfile):
    NAME = 'orange'
    MAINTAINER = 'Florian Duguet'
    EMAIL = 'florian.duguet@budget-insight.com'
    VERSION = '2.1'
    DESCRIPTION = 'Orange French mobile phone provider'
    LICENSE = 'LGPLv3+'
    CONFIG = BackendConfig(
        ValueBackendPassword('login', label='Login'),
        ValueBackendPassword('password', label='Password', regexp=r'\S{8,36}'),
    )
    BROWSER = OrangeBillBrowser

    def __init__(self, *args, **kwargs):
        self._browsers = dict()
        super(OrangeModule, self).__init__(*args, **kwargs)

    accepted_document_types = (DocumentTypes.BILL,)

    def create_default_browser(self):
        return self.create_browser(
            self.config['login'].get(),
            self.config['password'].get(),
        )

    def iter_subscription(self):
        return self.browser.get_subscription_list()

    def get_subscription(self, _id):
        return find_object(self.iter_subscription(), id=_id, error=SubscriptionNotFound)

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
        return self.browser.download_document(document)

    def get_profile(self):
        return self.browser.get_profile()
