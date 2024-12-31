# Copyright(C) 2024      Pierre BOULC'H
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

from woob.capabilities.bank import (
    CapBank,
)
from woob.tools.backend import Module, BackendConfig
from woob.tools.value import Value, ValueTransient

from .browser import GreenGotBrowser


__all__ = ['GreenGotModule']


class GreenGotModule(Module, CapBank):
    NAME = 'greengot'
    DESCRIPTION = 'GreenGot'
    MAINTAINER = 'Pierre BOULC\'H'
    EMAIL = 'dev@boulch.fr'
    CONFIG = BackendConfig(
        Value('login', label='Email', regexp='.+'),
        ValueTransient('smscode'),
        ValueTransient('emailcode')
    )
    BROWSER = GreenGotBrowser
    LICENSE = 'LGPLv3+'

    def create_default_browser(self):
        return self.create_browser(self.config, self.config['login'].get())

    def iter_accounts(self):
        return self.browser.iter_accounts()

    def iter_history(self, account):
        return self.browser.iter_history(account)

    def iter_pocket(self, account):
        return self.browser.iter_pocket(account)
