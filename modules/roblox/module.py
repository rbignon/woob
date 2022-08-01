# flake8: compatible

# Copyright(C) 2022 Thomas Touhey <thomas@touhey.fr>
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
from woob.tools.backend import BackendConfig, Module
from woob.tools.value import ValueBackendPassword, ValueTransient

from .browser import RobloxBrowser

__all__ = ['RobloxModule']


class RobloxModule(Module, CapBankWealth, CapProfile):
    NAME = 'roblox'
    DESCRIPTION = 'Roblox'
    MAINTAINER = 'Thomas Touhey'
    EMAIL = 'thomas@touhey.fr'
    LICENSE = 'LGPLv3+'
    VERSION = '3.1'

    CONFIG = BackendConfig(
        ValueBackendPassword(
            'login',
            label='Identifiant / E-mail / Téléphone',
            masked=False,
        ),
        ValueBackendPassword('password', label='Mot de passe'),
        ValueTransient('otp_email', regexp=r'^\d{6}$'),
        ValueTransient('otp_authenticator', regexp=r'^\d{6}$'),
        ValueTransient('captcha_response'),
        ValueTransient('request_information'),
    )

    BROWSER = RobloxBrowser

    def create_default_browser(self):
        return self.create_browser(self.config)

    def iter_accounts(self):
        yield self.browser.get_account()

    def iter_history(self, account):
        return self.browser.iter_history()

    def iter_investment(self, account):
        return self.browser.iter_investment()

    def get_profile(self):
        return self.browser.get_profile()
