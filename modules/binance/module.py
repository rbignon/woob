# Copyright(C) 2022      Florian Bezannier
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

from woob.tools.backend import Module, BackendConfig
from woob.capabilities.bank import CapBank
from woob.tools.value import Value, ValueBackendPassword

from .browser import BinanceBrowser


__all__ = ['BinanceModule']


class BinanceModule(Module, CapBank):
    NAME = 'binance'
    DESCRIPTION = 'Binance website'
    MAINTAINER = 'Florian Bezannier'
    EMAIL = 'florian.bezannier@hotmail.fr'
    LICENSE = 'LGPLv3+'

    BROWSER = BinanceBrowser
    CONFIG = BackendConfig(Value('api_key', label='Api key'),
                           ValueBackendPassword('secret_key', label='Secret Key'))

    def iter_accounts(self):
        return self.browser.iter_accounts()

    def create_default_browser(self):
        return self.create_browser(self.config)
