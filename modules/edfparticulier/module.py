# -*- coding: utf-8 -*-

# Copyright(C) 2020      Budget Insight

# flake8: compatible

from __future__ import unicode_literals


from weboob.capabilities.bill import (
    DocumentTypes, CapDocument, Subscription, Document, SubscriptionNotFound, DocumentNotFound,
)
from weboob.capabilities.base import find_object
from weboob.tools.backend import Module, BackendConfig
from weboob.tools.value import ValueBackendPassword, Value, ValueTransient
from weboob.capabilities.profile import CapProfile

from .browser import EdfParticulierBrowser


__all__ = ['EdfparticulierModule']


class EdfparticulierModule(Module, CapDocument, CapProfile):
    NAME = 'edfparticulier'
    DESCRIPTION = 'edf particulier'
    MAINTAINER = 'Florian Duguet'
    EMAIL = 'florian.duguet@budget-insight.com'
    LICENSE = 'LGPLv3+'
    VERSION = '1.6'

    BROWSER = EdfParticulierBrowser

    CONFIG = BackendConfig(
        Value('login', label='E-mail ou Identifiant'),
        ValueBackendPassword('password', label='Mot de passe'),
        ValueTransient('otp', label='Entrez le code reçu par SMS')
    )

    accepted_document_types = (DocumentTypes.BILL,)

    def create_default_browser(self):
        return self.create_browser(self.config)

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
        return self.browser.download_document(document)

    def get_profile(self):
        return self.browser.get_profile()
