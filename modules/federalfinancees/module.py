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

from woob.tools.backend import BackendConfig
from woob.tools.value import ValueBackendPassword, Value, ValueTransient
from woob.capabilities.bank.wealth import CapBankWealth
from woob.capabilities.bill import CapDocument
from woob.capabilities.profile import CapProfile
from woob_modules.s2e.module import S2eModule

from .browser import FederalFinanceESBrowser

__all__ = ['FederalFinanceESModule']


class FederalFinanceESModule(S2eModule, CapBankWealth, CapDocument, CapProfile):
    NAME = 'federalfinancees'
    DESCRIPTION = 'Federal Finance Épargne Salariale'
    MAINTAINER = 'Christophe Francois'
    EMAIL = 'christophe.francois@budget-insight.com'
    LICENSE = 'LGPLv3+'
    VERSION = '3.7'
    DEPENDENCIES = ('s2e',)

    CONFIG = BackendConfig(
        ValueBackendPassword('login', label='Identifiant', masked=False),
        ValueBackendPassword('password', label='Mot de passe', regexp=r'^(\d{6})$'),
        Value('otp', label='Code unique temporaire', default=''),
        ValueTransient('request_information'),
    )

    BROWSER = FederalFinanceESBrowser

    def create_default_browser(self):
        return self.create_browser(self.config)
