# Copyright(C) 2023      Hugues Mitonneau
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


from woob.tools.backend import Module, BackendConfig
from woob.capabilities.bill import CapDocument, Subscription, Bill, Document
from woob.tools.value import Value, ValueBool, ValueInt, ValueBackendPassword

from .browser import EspacecitoyensBrowser
from woob.exceptions import BrowserIncorrectPassword

__all__ = ['EspacecitoyensModule']


class EspacecitoyensModule(Module, CapDocument):
    NAME = 'espacecitoyens'
    DESCRIPTION = 'Espace Citoyens'
    MAINTAINER = 'Hugues Mitonneau'
    EMAIL = ''
    LICENSE = 'LGPLv3+'
    CONFIG = BackendConfig(
        Value('city', label='City'),
        Value('username', label='Username'),
        ValueBackendPassword('password', label='Password'),
    )

    BROWSER = EspacecitoyensBrowser
    
    def create_default_browser(self):
        return self.create_browser(
            self.config['username'].get(),
            self.config['password'].get(),
            self.config['city'].get(),
        )

    def check_credentials(self) -> bool:
        """
        Check that the given credentials are correct by trying to login.

        The default implementation of this method check if the class using this capability
        has a browser, execute its do_login if it has one and then see if no error pertaining to the creds is raised.
        If any other unexpected error occurs, we don't know whether the creds are correct or not.
        """
        if getattr(self, 'BROWSER', None) is None:
            raise NotImplementedError()

        try:
            self.browser.do_login()
        except BrowserIncorrectPassword:
            return False

        return True

    def download_document(self, id):
        """
        Download a document.

        :param id: ID of document
        :rtype: bytes
        :raises: :class:`DocumentNotFound`
        """
        return self.browser.download_document(id)

    def download_document_pdf(self, id):
        """
        Download a document, convert it to PDF if it isn't the document format.

        :param id: ID of document
        :rtype: bytes
        :raises: :class:`DocumentNotFound`
        """
        if not isinstance(id, Document):
            id = self.get_document(id)

        if id.format == 'pdf':
            return self.download_document(id)
        else:
            raise NotImplementedError()

    def get_document(self, id):
        """
        Get a document.

        :param id: ID of document
        :rtype: :class:`Document`
        :raises: :class:`DocumentNotFound`
        """
        return self.browser.get_document(id)

    def get_subscription(self, _id):
        return self.browser.get_subscription(_id)

    def iter_documents(self, subscription):
        """
        Iter documents.

        :param subscription: subscription to get documents
        :type subscription: :class:`Subscription`
        :rtype: iter[:class:`Document`]
        """
        return self.browser.iter_documents(subscription)

    def iter_subscription(self):
        """
        Iter subscriptions.

        :rtype: iter[:class:`Subscription`]
        """
        return self.browser.iter_subscriptions()

    def fill_subscription(self, subscription, fields):
        if 'label' in fields:
            return self.browser.get_subscription(subscription.id)
        return subscription

    def fill_bill(self, bill, fields):
        return self.browser.get_document(bill.id)

    def fill_document(self, document, fields):
        return self.browser.get_document(document.id)

    OBJECTS = {
        Subscription: fill_subscription,
        Bill: fill_bill,
        Document: fill_document,
    }
