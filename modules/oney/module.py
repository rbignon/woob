# -*- coding: utf-8 -*-

# Copyright(C) 2014 Budget Insight
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

from woob.capabilities.bank import CapBank
from woob.tools.backend import Module, BackendConfig
from woob.tools.value import ValueBackendPassword, ValueTransient

from .browser import OneyBrowser


__all__ = ['OneyModule']


class OneyModule(Module, CapBank):
    NAME = 'oney'
    MAINTAINER = 'Vincent Paredes'
    EMAIL = 'vparedes@budget-insight.com'
    VERSION = '3.1'
    LICENSE = 'LGPLv3+'
    DESCRIPTION = 'Oney'
    CONFIG = BackendConfig(
        ValueBackendPassword('login', label='Identifiant', masked=False, regexp=r'([0-9]{9}|.+@.+\..+)'),
        ValueBackendPassword('password', label='Mot de passe'),
        ValueBackendPassword('digitpassword', label="Code d'accès", regexp=r'\d{6}', required=False),
        ValueTransient('request_information'),
        ValueTransient('code', regexp=r'^\d{6}$'),
        ValueTransient('resume'),
    )
    BROWSER = OneyBrowser

    def create_default_browser(self):
        return self.create_browser(
            self.config,
            self.config['login'].get(),
            self.config['password'].get(),
        )

    def iter_accounts(self):
        return self.browser.iter_accounts()

    def iter_history(self, account):
        # To prevent issues in calcul of actual balance and coming one, all
        # operations are marked as debited.
        for tr in self.browser.iter_coming(account):
            yield tr

        for tr in self.browser.iter_history(account):
            yield tr
