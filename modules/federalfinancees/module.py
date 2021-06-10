# -*- coding: utf-8 -*-

# Copyright(C) 2021      Budget Insight
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


from woob.tools.backend import AbstractModule, BackendConfig
from woob.tools.value import ValueBackendPassword, Value
from woob.capabilities.wealth import CapBankWealth
from woob.capabilities.bill import CapDocument
from woob.capabilities.profile import CapProfile

from .browser import FederalFinanceESBrowser


__all__ = ['FederalFinanceESModule']


class FederalFinanceESModule(AbstractModule, CapBankWealth, CapDocument, CapProfile):
    NAME = 'federalfinancees'
    DESCRIPTION = 'Federal Finance Épargne Salariale'
    MAINTAINER = 'Christophe Francois'
    EMAIL = 'christophe.francois@budget-insight.com'
    LICENSE = 'Proprietary'
    VERSION = '1.6'

    CONFIG = BackendConfig(
        ValueBackendPassword('login', label='Identifiant', masked=False),
        ValueBackendPassword('password', label='Mot de passe', regexp=r'^(\d{6})$'),
        Value('otp', label='Code unique temporaire', default=''),
    )

    BROWSER = FederalFinanceESBrowser
    PARENT = 's2e'

    def create_default_browser(self):
        return self.create_browser(self.config, weboob=self.weboob)
