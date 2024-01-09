# Copyright(C) 2024      Ludovic LANGE
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

from typing import Iterable, List

from woob.capabilities.base import BaseObject, find_object
from woob.capabilities.bank import Account

from woob.capabilities.bill import (
    CapDocument,
    Subscription,
    Document,
    DocumentNotFound,
)
from woob_modules.cmso.module import CmsoModule
from woob.tools.backend import BackendConfig

from woob.tools.value import Value, ValueBackendPassword, ValueTransient

from .browser import CCFParBrowser, CCFProBrowser


__all__ = ["CCFModule"]


class CCFModule(CmsoModule, CapDocument):
    NAME = "ccf"
    DESCRIPTION = "CCF (ex- HSBC France)"
    MAINTAINER = "Ludovic LANGE"
    EMAIL = "llange@users.noreply.github.com"
    LICENSE = "LGPLv3+"
    DEPENDENCIES = ("cmso",)
    AVAILABLE_BROWSERS = {"par": CCFParBrowser, "pro": CCFProBrowser}
    CONFIG = BackendConfig(
        ValueBackendPassword(
            "login", label="Identifiant", regexp=r"^\d{9}$", masked=False
        ),
        ValueBackendPassword("password", label="Mot de passe", regexp=r"^\d{8}$"),
        ValueBackendPassword(
            "security_code", label="Code de sécurité", regexp=r"^\d{5}$"
        ),
        ValueTransient("code"),
        ValueTransient("request_information"),
        Value(
            "website",
            label="Type de compte",
            default="par",
            choices={
                "par": "Particuliers",
                "pro": "Professionnels",
            },
        ),
    )

    def download_document(self, document):
        """
        Download a document.

        :param document: ID of document
        :rtype: bytes
        :raises: :class:`DocumentNotFound`
        """
        if not isinstance(document, Document):
            document = self.get_document(document)
        return self.browser.download_document(document)

    def get_document(self, _id):
        """
        Get a document.

        :param id: ID of document
        :rtype: :class:`Document`
        :raises: :class:`DocumentNotFound`
        """
        subid = _id.rsplit("_", 1)[0]
        subscription = self.get_subscription(subid)

        return find_object(
            self.iter_documents(subscription), id=_id, error=DocumentNotFound
        )

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

    def iter_resources(
        self, objs: List[BaseObject], split_path: List[str]
    ) -> Iterable[BaseObject]:
        """
        Iter resources.

        Default implementation of this method is to return on top-level
        all accounts (by calling :func:`iter_accounts`).

        :param objs: type of objects to get
        :type objs: tuple[:class:`BaseObject`]
        :param split_path: path to discover
        :type split_path: :class:`list`
        :rtype: iter[:class:`BaseObject`]
        """
        if Account in objs:
            self._restrict_level(split_path)

            yield from self.iter_accounts()

        if Subscription in objs:
            self._restrict_level(split_path)

            yield from self.iter_subscription()

    def iter_subscription(self):
        """
        Iter subscriptions.

        :rtype: iter[:class:`Subscription`]
        """
        return self.browser.get_subscription_list()
