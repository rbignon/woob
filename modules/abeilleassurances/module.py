# Copyright(C) 2023 Powens
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

from woob.capabilities.bank import Account
from woob.capabilities.bank.wealth import CapBankWealth
from woob.capabilities.base import find_object
from woob.capabilities.bill import CapDocument, Document, DocumentNotFound, Subscription
from woob.tools.backend import BackendConfig, Module
from woob.tools.value import ValueBackendPassword

from .browser import AbeilleAssurancesBrowser


__all__ = ["AbeilleAssurancesModule"]


class AbeilleAssurancesModule(Module, CapBankWealth, CapDocument):
    NAME = "abeilleassurances"
    DESCRIPTION = "Abeille Assurances"
    MAINTAINER = "Nicolas Vergnac"
    EMAIL = "nicolas.vergnac@budget-insight.com"
    LICENSE = "LGPLv3+"
    VERSION = "3.7"
    CONFIG = BackendConfig(
        ValueBackendPassword("login", label="Identifiant", masked=False),
        ValueBackendPassword("password", label="Mot de passe"),
    )

    BROWSER = AbeilleAssurancesBrowser

    def create_default_browser(self):
        return self.create_browser(self.config["login"].get(), self.config["password"].get())

    def iter_accounts(self):
        return self.browser.iter_accounts()

    def iter_history(self, account):
        return self.browser.iter_history(account)

    def iter_investment(self, account):
        return self.browser.iter_investment(account)

    def iter_resources(self, objs, split_path):
        """
        Iter resources. Will return :func:`iter_subscriptions`.
        """
        if Subscription in objs:
            self._restrict_level(split_path)
            yield from self.iter_subscription()

        if Account in objs:
            self._restrict_level(split_path)
            yield from self.iter_accounts()

    def iter_subscription(self):
        """
        Iter subscriptions.

        :rtype: iter[:class:`Subscription`]
        """
        return self.browser.iter_subscriptions()

    def get_document(self, id):
        """
        Get a document.

        :param id: ID of document
        :rtype: :class:`Document`
        :raises: :class:`DocumentNotFound`
        """
        subid = id.split("_")[0]
        subscription = self.get_subscription(subid)

        return find_object(self.iter_documents(subscription), id=id, error=DocumentNotFound)

    def download_document(self, doc):
        """
        Download a document.

        :param id: ID of document
        :rtype: bytes
        :raises: :class:`DocumentNotFound`
        """
        if not isinstance(doc, Document):
            doc = self.get_document(doc)
        return self.browser.open(doc.url).content

    def iter_documents(self, subscription):
        """
        Iter documents.

        :param subscription: subscription to get documents
        :type subscription: :class:`Subscription`
        :rtype: iter[:class:`Document`]
        """
        if not isinstance(subscription, Subscription):
            subscription = self.get_subscription(subscription)
        return self.browser.iter_documents(subscription)
