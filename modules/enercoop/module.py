# Copyright(C) 2020      Vincent A
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
from woob.capabilities.bill import CapDocument, DocumentNotFound, DocumentTypes
from woob.capabilities.gauge import CapGauge
from woob.capabilities.profile import CapProfile
from woob.tools.backend import BackendConfig, Module
from woob.tools.value import ValueBackendPassword

from .browser import EnercoopBrowser


__all__ = ["EnercoopModule"]


class EnercoopModule(Module, CapDocument, CapGauge, CapProfile):
    NAME = "enercoop"
    DESCRIPTION = "Enercoop"
    MAINTAINER = "Vincent A"
    EMAIL = "dev@indigo.re"
    LICENSE = "LGPLv3+"

    BROWSER = EnercoopBrowser

    CONFIG = BackendConfig(
        ValueBackendPassword("email", label="Adresse email", regexp=".+@.+", masked=False),
        ValueBackendPassword("password", label="Mot de passe"),
    )

    accepted_document_types = (DocumentTypes.BILL,)

    def create_default_browser(self):
        return self.create_browser(self.config["email"].get(), self.config["password"].get())

    def get_profile(self):
        return self.browser.get_profile()

    def iter_subscription(self):
        return self.browser.iter_subscription()

    def iter_documents(self, subscription):
        return self.browser.iter_documents(subscription)

    def get_document(self, id):
        """
        Get a document.

        :param id: ID of document
        :rtype: :class:`Document`
        :raises: :class:`DocumentNotFound`
        """
        return find_object(self.iter_documents(id.split("_")[-1]), id=id, error=DocumentNotFound)

    def download_document(self, id):
        return self.browser.download_document(id)

    def iter_gauges(self, pattern=""):
        return self.browser.iter_gauges()

    def iter_sensors(self, id, pattern=None):
        return self.browser.iter_sensors(id)

    def iter_gauge_history(self, id):
        return self.browser.iter_sensor_history(id)
