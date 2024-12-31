# -*- coding: utf-8 -*-

# Copyright(C) 2015      Vincent Paredes
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
from woob.capabilities.bill import Bill, CapDocument, DocumentCategory, DocumentNotFound, DocumentTypes, Subscription
from woob.tools.backend import BackendConfig, Module
from woob.tools.value import Value, ValueBackendPassword, ValueTransient

from .browser import OvhBrowser


__all__ = ['OvhModule']


class OvhModule(Module, CapDocument):
    NAME = 'ovh'
    DESCRIPTION = 'Ovh'
    MAINTAINER = 'Vincent Paredes'
    EMAIL = 'vparedes@budget-insight.com'
    LICENSE = 'LGPLv3+'
    VERSION = '3.7'
    CONFIG = BackendConfig(
        ValueBackendPassword('login', label='Account ID'),
        ValueBackendPassword('password', label='Password'),
        Value('pin_code', label='Code PIN / Email', required=False, default=''),
        ValueTransient('2fa_type', label=u'Type of 2FA', choices=['totp', 'sms', 'u2f', 'staticOTP'], required=False, default=None),
        ValueTransient('2fa_value', label=u'Value of 2FA', required=False),
    )

    BROWSER = OvhBrowser

    accepted_document_types = (DocumentTypes.BILL,)
    document_categories = {DocumentCategory.SOFTWARE}

    def create_default_browser(self):
        return self.create_browser(self.config)

    def iter_subscription(self):
        return self.browser.get_subscription_list()

    def get_document(self, _id):
        subid = _id.split('.')[0]
        subscription = self.get_subscription(subid)

        return find_object(self.iter_documents(subscription), id=_id, error=DocumentNotFound)

    def iter_documents(self, subscription):
        if not isinstance(subscription, Subscription):
            subscription = self.get_subscription(subscription)
        return self.browser.iter_documents(subscription)

    def download_document(self, bill):
        if not isinstance(bill, Bill):
            bill = self.get_document(bill)
        return self.browser.open(bill.url).content
