# Copyright(C) 2023 Powens
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

from woob.capabilities.bank.wealth import CapBankWealth
from woob.capabilities.profile import CapProfile
from woob.tools.backend import BackendConfig
from woob.tools.value import ValueBackendPassword
from woob_modules.creditdunord.module import CreditDuNordModule

from .browser import NugerBrowser


__all__ = ["NugerModule"]


class NugerModule(CreditDuNordModule, CapBankWealth, CapProfile):
    NAME = "nuger"
    MAINTAINER = "Romain Bignon"
    EMAIL = "romain@weboob.org"
    VERSION = "3.7"
    DEPENDENCIES = ("creditdunord",)
    DESCRIPTION = "Banque Nuger"
    LICENSE = "LGPLv3+"
    CONFIG = BackendConfig(
        ValueBackendPassword("login", label="Identifiant", masked=False),
        ValueBackendPassword("password", label="Code confidentiel", regexp=r"\d{6}"),
    )
    BROWSER = NugerBrowser
