# -*- coding: utf-8 -*-

# Copyright(C) 2021      Florent Fourcot
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

import hashlib
import hmac

from woob.tools.backend import Module, BackendConfig
from woob.capabilities.base import find_object
from woob.capabilities.bill import CapDocument, SubscriptionNotFound,\
                                     Document, DocumentNotFound
from woob.tools.value import Value, ValueBackendPassword

from .browser import PayFitBrowser


__all__ = ['PayFitModule']


class PayFitModule(Module, CapDocument):
    NAME = 'payfit'
    DESCRIPTION = 'payfit website'
    MAINTAINER = 'Florent Fourcot'
    EMAIL = 'woob@flo.fourcot.fr'
    LICENSE = 'LGPLv3+'
    VERSION = '3.1'

    BROWSER = PayFitBrowser
    CONFIG = BackendConfig(Value('login', label='Email address', required=True),
                           ValueBackendPassword('password', label='Password'))

    def create_default_browser(self):
        mac = hmac.new(self.config['password'].get().encode(), msg=b'', digestmod=hashlib.sha256)
        return self.create_browser(self.config['login'].get(), mac.hexdigest())

    def get_document(self, _id):
        _, sub_id = _id.split("-", maxsplit=1)
        return find_object(self.iter_documents(sub_id), id=_id,
                           error=DocumentNotFound)

    def get_subscription(self, _id):
        return find_object(self.browser.iter_subscription(), id=_id,
                           error=SubscriptionNotFound)

    def iter_documents(self, subscription):
        if isinstance(subscription, str):
            subscription = self.get_subscription(subscription)
        return self.browser.iter_documents(subscription)

    def iter_subscription(self):
        return self.browser.iter_subscription()

    def download_document(self, doc):
        if not isinstance(doc, Document):
            doc = self.get_document(doc)
        return self.browser.open(doc.url).content
