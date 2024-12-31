# Copyright(C) 2019 Powens
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
    CapDocument, Document, DocumentCategory, DocumentNotFound, DocumentTypes, Subscription,
)
from woob.capabilities.messages import CapMessagesPost
from woob.capabilities.profile import CapProfile
from woob.tools.backend import BackendConfig, Module
from woob.tools.value import ValueBackendPassword, ValueTransient

from .browser import BouyguesBrowser


__all__ = ['BouyguesModule']


class BouyguesModule(Module, CapDocument, CapMessagesPost, CapProfile):
    NAME = 'bouygues'
    DESCRIPTION = 'Bouygues Télécom'
    MAINTAINER = 'Florian Duguet'
    EMAIL = 'florian.duguet@budget-insight.com'
    LICENSE = 'LGPLv3+'
    VERSION = '3.7'
    CONFIG = BackendConfig(
        ValueBackendPassword(
            'login',
            label='Numéro de mobile (sans espace), de clé/tablette ou e-mail en @bbox.fr',
            masked=False,
        ),
        ValueBackendPassword('password', label='Mot de passe'),
        ValueBackendPassword('lastname', label='Nom de famille', default='', masked=False),
        ValueTransient('otp_sms', regexp=r'^[0-9]{6}$'),
        ValueTransient('otp_email', regexp=r'^[0-9]{6}$'),
        ValueTransient('request_information'),
    )
    BROWSER = BouyguesBrowser
    accepted_document_types = (DocumentTypes.BILL,)
    document_categories = {DocumentCategory.INTERNET_TELEPHONY}

    def create_default_browser(self):
        return self.create_browser(
            # Sending a phone number with spaces between numbers will
            # automatically redirect us to the login page with no error
            self.config,
            self.config['login'].get().replace(' ', ''),
            self.config['password'].get(),
            self.config['lastname'].get(),
        )

    def iter_subscription(self):
        return self.browser.iter_subscriptions()

    def iter_documents(self, subscription):
        if not isinstance(subscription, Subscription):
            subscription = self.get_subscription(subscription)
        return self.browser.iter_documents(subscription)

    def get_document(self, _id):
        subid = _id.rsplit('_', 1)[0]
        subscription = self.get_subscription(subid)
        return find_object(self.iter_documents(subscription), id=_id, error=DocumentNotFound)

    def download_document(self, document):
        if not isinstance(document, Document):
            document = self.get_document(document)
        return self.browser.download_document(document)

    def post_message(self, message):
        receivers = message.receivers
        if not receivers:
            assert message.thread
            receivers = [message.thread.id]
        self.browser.post_message(receivers, message.content)

    def get_profile(self):
        return self.browser.get_profile()
