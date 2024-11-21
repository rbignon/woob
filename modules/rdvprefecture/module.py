# Copyright(C) 2024 Thomas Touhey <thomas+woob@touhey.fr>
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

from __future__ import annotations

from woob.tools.backend import BackendConfig, Module
from woob.tools.value import ValueTransient

from .browser import RDVPrefectureBrowser


__all__ = ['RDVPrefectureModule']


class RDVPrefectureModule(Module):
    NAME = 'rdvprefecture'
    DESCRIPTION = 'RDV Prefecture'
    MAINTAINER = 'Thomas Touhey'
    EMAIL = 'thomas+woob@touhey.fr'
    LICENSE = 'LGPLv3+'

    CONFIG = BackendConfig(ValueTransient('captcha_response'))
    BROWSER = RDVPrefectureBrowser

    def create_default_browser(self):
        return self.create_browser(self.config)

    def check_slots_available(self, procedure_id: int) -> bool:
        """Check if slots are available.

        :param procedure_id: Procedure identifier.
        :return: Whether slots are available.
        """
        return self.browser.check_slots_available(procedure_id)
