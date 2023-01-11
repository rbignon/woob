# -*- coding: utf-8 -*-

# Copyright(C) 2012-2019 Romain Bignon
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

from __future__ import unicode_literals

from woob.capabilities.bank import CapBank
from woob.tools.backend import AbstractModule, BackendConfig
from woob.tools.value import ValueBackendPassword, ValueTransient

from .browser import GanAssurancesBrowser


__all__ = ['GanAssurancesModule']


class GanAssurancesModule(AbstractModule, CapBank):
    NAME = 'ganassurances'
    MAINTAINER = 'Romain Bignon'
    EMAIL = 'romain@weboob.org'
    VERSION = '3.1'
    DEPENDENCIES = ('ganpatrimoine',)
    DESCRIPTION = 'Gan Assurances'
    LICENSE = 'LGPLv3+'
    CONFIG = BackendConfig(
        ValueBackendPassword('login', label='Numéro client', masked=False),
        ValueBackendPassword('password', label="Code d'accès", regexp=r'\d{6}'),
        ValueTransient('otp_sms', regexp=r'\d{6}'),
        ValueTransient('request_information'),
    )

    PARENT = 'ganpatrimoine'
    BROWSER = GanAssurancesBrowser


    def create_default_browser(self):
        return self.create_browser(
            'ganassurances',
            self.config,
            self.config['login'].get(),
            self.config['password'].get(),
            woob=self.woob
        )
