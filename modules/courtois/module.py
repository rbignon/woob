# -*- coding: utf-8 -*-

# Copyright(C) 2012-2020  Budget Insight
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

from woob.capabilities.bank.wealth import CapBankWealth
from woob.capabilities.profile import CapProfile
from woob.tools.backend import AbstractModule, BackendConfig
from woob.tools.value import ValueBackendPassword

from .browser import CourtoisBrowser

__all__ = ['CourtoisModule']


class CourtoisModule(AbstractModule, CapBankWealth, CapProfile):
    NAME = 'courtois'
    MAINTAINER = u'Romain Bignon'
    EMAIL = 'romain@weboob.org'
    VERSION = '3.7'
    DEPENDENCIES = ('creditdunord',)
    DESCRIPTION = u'Banque Courtois'
    LICENSE = 'LGPLv3+'
    CONFIG = BackendConfig(ValueBackendPassword('login',    label='Identifiant', masked=False),
                           ValueBackendPassword('password', label='Code confidentiel'))
    PARENT = 'creditdunord'
    BROWSER = CourtoisBrowser

    def create_default_browser(self):
        return self.create_browser(
            self.config['login'].get(),
            self.config['password'].get(),
            woob=self.woob
    )
