# -*- coding: utf-8 -*-

# Copyright(C) 2016      Edouard Lambert
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

from woob.tools.backend import Module
from woob.capabilities.bank.wealth import CapBankWealth
from woob.capabilities.profile import CapProfile
from woob.capabilities.bank import Account
from woob.capabilities.base import find_object, empty
from woob.capabilities.bill import (
    CapDocument, Subscription, Document, DocumentNotFound, DocumentTypes,
)


class S2eModule(Module, CapBankWealth, CapDocument, CapProfile):
    NAME = 's2e'
    DESCRIPTION = u'Épargne Salariale'
    MAINTAINER = u'Edouard Lambert'
    EMAIL = 'elambert@budget-insight.com'
    LICENSE = 'LGPLv3+'
    VERSION = '3.3.1'

    accepted_document_types = (DocumentTypes.STATEMENT, DocumentTypes.REPORT)

    def iter_accounts(self):
        return self.browser.iter_accounts()

    def iter_history(self, account):
        return self.browser.iter_history(account)

    def iter_investment(self, account):
        return self.browser.iter_investment(account)

    def iter_pocket(self, account):
        return self.browser.iter_pocket(account)

    def get_profile(self):
        return self.browser.get_profile()

    # From woob.capabilities.bill.CapDocument
    def iter_subscription(self):
        """Fake subscription - documents are attached to a subscription."""
        sub = Subscription()
        sub.id = 'statements'
        sub.label = u'Relevés électroniques / e-statements'
        yield sub

    # From woob.capabilities.bill.CapDocument
    def iter_documents(self, subscription):
        return self.browser.iter_documents()

    # From woob.capabilities.bill.CapDocument
    def get_document(self, _id):
        return find_object(self.iter_documents(None), id=_id, error=DocumentNotFound)

    # From woob.capabilities.bill.CapDocument
    def download_document(self, document):
        if not isinstance(document, Document):
            document = self.get_document(document)
        if empty(document.url):
            return
        return self.browser.open(document.url).content

    # From woob.capabilities.collection.CapCollection
    def iter_resources(self, objs, split_path):
        """Merging implementation from CapDocument and CapBank."""
        if Account in objs:
            self._restrict_level(split_path)
            return self.iter_accounts()
        if Subscription in objs:
            self._restrict_level(split_path)
            return self.iter_subscription()
