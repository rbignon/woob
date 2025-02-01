# Copyright(C) 2022-2023 Powens
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

from woob.capabilities.bank.base import CapBank
from woob.tools.backend import BackendConfig, Module
from woob.tools.value import ValueBackendPassword, ValueTransient

from .browser import MaFrenchBankBrowser


__all__ = ["MaFrenchBankModule"]


class MaFrenchBankModule(Module, CapBank):
    NAME = "mafrenchbank"
    DESCRIPTION = "Ma French Bank"
    MAINTAINER = "Powens"
    EMAIL = "dev@powens.com"
    LICENSE = "LGPLv3+"
    VERSION = "3.7"

    CONFIG = BackendConfig(
        ValueBackendPassword("login", label="Alias", masked=False),
        ValueBackendPassword("password", label="Mot de passe"),
        ValueTransient("otp_app", regexp=r"\d{8}"),
    )

    BROWSER = MaFrenchBankBrowser

    def create_default_browser(self):
        return self.create_browser(self.config)

    def iter_accounts(self):
        return self.browser.iter_accounts()

    def iter_history(self, account):
        return self.browser.iter_history(account)
