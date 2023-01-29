# -*- coding: utf-8 -*-

# Copyright(C) 2021 Vincent A
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

from __future__ import unicode_literals

from woob.capabilities.parcel import CapParcel
from woob.tools.backend import Module, BackendConfig
from woob.tools.value import Value

from .browser import MondialrelayBrowser


__all__ = ["MondialrelayModule"]


class MondialrelayModule(Module, CapParcel):
    NAME = "mondialrelay"
    DESCRIPTION = "Mondial Relay"
    MAINTAINER = "Vincent A"
    EMAIL = "dev@indigo.re"
    LICENSE = "LGPLv3+"
    VERSION = "3.2"

    BROWSER = MondialrelayBrowser

    CONFIG = BackendConfig(
        Value("postal_code", label="Default postal code of recipient (optional)", default=""),
    )

    def create_default_browser(self):
        return self.create_browser(
            self.config["postal_code"].get(),
        )

    def get_parcel_tracking(self, id):
        return self.browser.get_parcel_tracking(id)
