# -*- coding: utf-8 -*-

# Copyright(C) 2016      Edouard Lambert
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


from woob.capabilities.bank import CapBank
from woob.tools.backend import AbstractModule, BackendConfig
from woob.tools.value import ValueBackendPassword, Value, ValueTransient

from .proxy_browser import ProxyBrowser


__all__ = ['BtpbanqueModule']


class BtpbanqueModule(AbstractModule, CapBank):
    NAME = 'btpbanque'
    DESCRIPTION = u'BTP Banque'
    MAINTAINER = u'Edouard Lambert'
    EMAIL = 'elambert@budget-insight.com'
    VERSION = '2.1'
    LICENSE = 'LGPLv3+'
    auth_type = {'weak' : "Code confidentiel (pro)",
                 'strong': "Sesame (pro)"}
    CONFIG = BackendConfig(
        Value('auth_type', label='Type de compte', choices=auth_type, default="weak"),
        ValueBackendPassword('login', label='Code utilisateur', masked=False),
        ValueBackendPassword('password', label='Code confidentiel ou code PIN', regexp='\d+'),
        Value('nuser', label="Numéro d'utilisateur (optionnel)", regexp='\d{0,8}', default=''),
        ValueTransient('emv_otp', regexp=r'\d{8}'),
        ValueTransient('request_information'),
    )
    PARENT = 'caissedepargne'
    BROWSER = ProxyBrowser

    def create_default_browser(self):
        return self.create_browser(
            nuser=self.config['nuser'].get(),
            config=self.config,
            username=self.config['login'].get(),
            password=self.config['password'].get(),
            weboob=self.weboob
        )
