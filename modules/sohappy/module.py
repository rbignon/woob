# -*- coding: utf-8 -*-

# Copyright(C) 2022      Guillaume Thomas
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


from woob.tools.backend import BackendConfig, Module
from woob.tools.value import ValueBackendPassword, Value
from woob.capabilities.base import find_object
from woob.capabilities.bill import (
    CapDocument,
    Document,
    DocumentNotFound,
    Subscription,
)
from woob.capabilities.profile import CapProfile

from .browser import SohappyBrowser


__all__ = ["SohappyModule"]


class SohappyModule(Module, CapDocument, CapProfile):
    NAME = "sohappy"
    DESCRIPTION = "sohappy website"
    MAINTAINER = "Guillaume Thomas"
    EMAIL = "guillaume.thomas642@gmail.com"
    LICENSE = "LGPLv3+"
    VERSION = "3.2"

    BROWSER = SohappyBrowser

    CONFIG = BackendConfig(
        Value("username", label="Identifiant"),
        ValueBackendPassword("password", label="Mot de passe"),
    )

    def create_default_browser(self):
        return self.create_browser(
            self.config["username"].get(), self.config["password"].get()
        )

    def get_profile(self):
        return self.browser.get_profile()

    def iter_subscription(self):
        return self.browser.get_subscription_list()

    def get_document(self, _id):
        child, client, docid = _id.split("_")

        return find_object(self.iter_documents(child), id=_id, error=DocumentNotFound)

    def iter_documents(self, subscription):
        if not isinstance(subscription, Subscription):
            subscription = self.get_subscription(subscription)
        return self.browser.iter_documents(subscription)

    def download_document(self, document):
        if not isinstance(document, Document):
            document = self.get_document(document)
        return self.browser.download_document(document)

    def get_balance(self, subscription):
        if not isinstance(subscription, Subscription):
            subscription = self.get_subscription(subscription)
        return self.browser.get_balance(subscription)
