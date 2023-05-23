# -*- coding: utf-8 -*-

# Copyright(C) 2013-2014 Florent Fourcot
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
    CapDocument, Subscription, Detail, DocumentCategory,
)
from woob.tools.backend import Module, BackendConfig
from woob.tools.value import ValueBackendPassword

from .browser import PoivyBrowser


__all__ = ['PoivyModule']


class PoivyModule(Module, CapDocument):
    NAME = 'poivy'
    MAINTAINER = u'Florent Fourcot'
    EMAIL = 'weboob@flo.fourcot.fr'
    VERSION = '3.6'
    LICENSE = 'LGPLv3+'
    DESCRIPTION = 'Poivy website'
    CONFIG = BackendConfig(ValueBackendPassword('login',
                                                label='login',
                                                masked=False),
                           ValueBackendPassword('password',
                                                label='Password')
                           )
    BROWSER = PoivyBrowser

    document_categories = {DocumentCategory.INTERNET_TELEPHONY}

    def create_default_browser(self):
        return self.create_browser(self.config['login'].get(),
                                   self.config['password'].get())

    def iter_subscription(self):
        return self.browser.get_subscription_list()

    def iter_documents_history(self, subscription):
        # Try if we have a real subscription before to load the history
        if not isinstance(subscription, Subscription):
            subscription = self.get_subscription(subscription)
        return self.browser.get_history()

    # No details on the website
    def get_details(self, subscription):
        raise NotImplementedError()

    def get_balance(self, subscription):
        if not isinstance(subscription, Subscription):
            subscription = self.get_subscription(subscription)
        balance = Detail()
        balance.id = "%s-balance" % subscription.id
        balance.price = subscription._balance
        balance.label = u"Balance %s" % subscription.id
        balance.currency = u'EUR'
        return balance
