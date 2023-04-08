# -*- coding: utf-8 -*-

# flake8: compatible

# Copyright(C) 2012-2014 Florent Fourcot
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

from woob.capabilities.bill import (
    DocumentTypes, CapDocument, Subscription,
    Bill, DocumentNotFound, DocumentCategory,
)
from woob.capabilities.profile import CapProfile
from woob.capabilities.messages import CantSendMessage, CapMessages, CapMessagesPost
from woob.capabilities.base import find_object
from woob.tools.backend import Module, BackendConfig
from woob.tools.value import ValueBackendPassword

from .browser import Freemobile


__all__ = ['FreeMobileModule']


class FreeMobileModule(Module, CapDocument, CapProfile, CapMessages, CapMessagesPost):
    NAME = 'freemobile'
    MAINTAINER = u'Florent Fourcot'
    EMAIL = 'weboob@flo.fourcot.fr'
    VERSION = '3.5'
    LICENSE = 'LGPLv3+'
    DESCRIPTION = 'Free Mobile website'
    CONFIG = BackendConfig(
        ValueBackendPassword(
            'login',
            label='Account ID',
            masked=False,
            regexp=r'^(\d{8}|)$'
        ),
        ValueBackendPassword(
            'password',
            label='Password'
        )
    )
    BROWSER = Freemobile

    accepted_document_types = (DocumentTypes.BILL,)
    document_categories = {DocumentCategory.INTERNET_TELEPHONY}

    def create_default_browser(self):
        return self.create_browser(
            self.config['login'].get(),
            self.config['password'].get()
        )

    def iter_subscription(self):
        return self.browser.iter_subscription()

    def get_document(self, _id):
        subid = _id.split('_')[0]
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

    def post_message(self, message):
        if not message.content.strip():
            raise CantSendMessage(u'Message content is empty.')
        return self.browser.post_message(message)

    def get_profile(self):
        return self.browser.get_profile()
