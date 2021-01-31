# -*- coding: utf-8 -*-

# Copyright(C) 2020      Vincent A
#
# This file is part of a weboob module.
#
# This weboob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This weboob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this weboob module. If not, see <http://www.gnu.org/licenses/>.

# flake8: compatible

from __future__ import unicode_literals

from weboob.tools.backend import Module, BackendConfig
from weboob.tools.value import ValueBackendPassword
from weboob.capabilities.bill import (
    DocumentTypes, CapDocument, Subscription,
)
from weboob.capabilities.gauge import CapGauge

from .browser import EnercoopBrowser


__all__ = ['EnercoopModule']


class EnercoopModule(Module, CapDocument, CapGauge):
    NAME = 'enercoop'
    DESCRIPTION = 'Enercoop'
    MAINTAINER = 'Vincent A'
    EMAIL = 'dev@indigo.re'
    LICENSE = 'LGPLv3+'
    VERSION = '2.1'

    BROWSER = EnercoopBrowser

    CONFIG = BackendConfig(
        ValueBackendPassword('email', regexp='.+@.+', masked=False),
        ValueBackendPassword('password'),
    )

    accepted_document_types = (DocumentTypes.BILL,)

    def create_default_browser(self):
        return self.create_browser(self.config['email'].get(), self.config['password'].get())

    def iter_subscription(self):
        return self.browser.iter_subscription()

    def iter_documents(self, subscription):
        if isinstance(subscription, Subscription):
            subscription = subscription.id
        return self.browser.iter_documents(subscription)

    def download_document(self, id):
        return self.browser.download_document(id)

    def iter_gauges(self, pattern=""):
        return self.browser.iter_gauges()

    def iter_sensors(self, id, pattern=None):
        return self.browser.iter_sensors(id)

    def iter_gauge_history(self, id):
        return self.browser.iter_sensor_history(id)
