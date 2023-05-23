# -*- coding: utf-8 -*-

# Copyright(C) 2021      Damien Ramelet
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

from woob.capabilities.profile import CapProfile
from woob.capabilities.bank.wealth import CapBankWealth
from woob.tools.backend import BackendConfig, Module
from woob.tools.value import ValueBackendPassword

from .browser import LitaBrowser

__all__ = ['LitaModule']


class LitaModule(Module, CapBankWealth, CapProfile):
    NAME = 'lita'
    DESCRIPTION = 'Lita is an investment platform that allows you to contribute financially to sustainable, ecological, social and/or solidarity projects.'
    MAINTAINER = 'Damien Ramelet'
    EMAIL = 'damien.ramelet@protonmail.com'
    LICENSE = 'LGPLv3+'
    VERSION = '3.6'

    BROWSER = LitaBrowser
    CONFIG = BackendConfig(
        ValueBackendPassword('username', label='Email', masked=False, regexp='.+@.+', required=True),
        ValueBackendPassword('password', label='Votre mot de passe', required=True)
    )

    def create_default_browser(self):
        return self.create_browser(self.config['username'].get(), self.config['password'].get())

    def iter_accounts(self):
        return self.browser.get_user_account()

    def iter_investment(self, account):
        return self.browser.iter_investments()

    def get_profile(self):
        return self.browser.get_profile()
