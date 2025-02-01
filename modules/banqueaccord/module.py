# Copyright(C) 2013-2023 Romain Bignon
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

from woob.capabilities.bank import CapBankWealth
from woob.tools.backend import BackendConfig
from woob.tools.value import ValueBackendPassword
from woob_modules.oney.module import OneyModule


__all__ = ["BanqueAccordModule"]


class BanqueAccordModule(OneyModule, CapBankWealth):
    NAME = "banqueaccord"
    DESCRIPTION = "Banque Accord"
    MAINTAINER = "Romain Bignon"
    EMAIL = "romain@weboob.org"
    LICENSE = "LGPLv3+"
    VERSION = "3.7"

    DEPENDENCIES = ("oney",)

    CONFIG = BackendConfig(
        ValueBackendPassword("login", label="Identifiant", regexp=r"\d+", masked=False),
        ValueBackendPassword("password", label="Code d'accès", regexp=r"\d+"),
    )
