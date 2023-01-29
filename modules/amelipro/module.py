# Copyright(C) 2022      Budget Insight

# Copyright(C) 2013-2015      Christophe Lampin
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

from woob.capabilities.base import find_object
from woob.capabilities.bill import (
    Bill, CapDocument, DocumentCategory, DocumentNotFound,
    DocumentTypes, Subscription,
)
from woob.tools.backend import Module, BackendConfig
from woob.tools.value import ValueBackendPassword, ValueTransient

from .browser import AmeliProBrowser

__all__ = ['AmeliProModule']


class AmeliProModule(Module, CapDocument):
    NAME = 'amelipro'
    DESCRIPTION = 'Ameli website: French Health Insurance for Professionals'
    MAINTAINER = 'Christophe Lampin'
    EMAIL = 'weboob@lampin.net'
    VERSION = '3.2'
    LICENSE = 'LGPLv3+'
    BROWSER = AmeliProBrowser
    CONFIG = BackendConfig(
        ValueBackendPassword('login', label="E-mail, N° d'Assurance Maladie ou N° FINESS", masked=False),
        ValueBackendPassword('password', label='Mot de passe'),
        ValueTransient('captcha_response'),
    )

    accepted_document_types = (DocumentTypes.BILL,)
    document_categories = {DocumentCategory.ADMINISTRATIVE}

    def create_default_browser(self):
        return self.create_browser(
            self.config,
            self.config['login'].get(),
            self.config['password'].get(),
        )

    def iter_subscription(self):
        return self.browser.iter_subscription()

    def iter_documents(self, subscription):
        if not isinstance(subscription, Subscription):
            subscription = self.get_subscription(subscription)
        return self.browser.iter_documents(subscription)

    def get_document(self, _id):
        subid = _id.rsplit('_')[0]
        subscription = self.get_subscription(subid)
        return find_object(self.iter_documents(subscription), id=_id, error=DocumentNotFound)

    def download_document(self, bill):
        if not isinstance(bill, Bill):
            bill = self.get_document(bill)
        return self.browser.open(bill.url).content
