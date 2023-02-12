# Copyright(C) 2022      Jeremy Demange (scrapfast.io)
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

from woob.capabilities.bank import CapBank
from woob.capabilities.profile import CapProfile
from woob.tools.backend import Module, BackendConfig
from woob.tools.value import Value, ValueBackendPassword

from .browser import TiimeBrowser

__all__ = ['TiimeModule']


class TiimeModule(Module, CapBank, CapProfile):
    NAME = 'tiime'
    DESCRIPTION = 'Tiime'
    MAINTAINER = 'Jeremy Demange'
    EMAIL = 'jeremy@scrapfast.io'
    LICENSE = 'LGPLv3+'
    VERSION = '3.3.1'

    CONFIG = BackendConfig(
        Value('login', label='Identifiant', masked=False),
        ValueBackendPassword('password', label='Mot de passe')
    )

    BROWSER = TiimeBrowser

    def create_default_browser(self):
        return self.create_browser(self.config['login'].get(), self.config['password'].get())

    def get_profile(self):
        return self.browser.get_profile()

    def iter_accounts(self):
        return self.browser.iter_accounts()

    def iter_history(self, account_id):
        return self.browser.iter_history(account_id)
