# -*- coding: utf-8 -*-

# Copyright(C) 2015      Oleg Plakhotniuk
#
# This file is part of a woob module.
#
# This woob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This woob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this woob module. If not, see <http://www.gnu.org/licenses/>.


from woob.capabilities.shop import CapShop
from woob.tools.backend import BackendConfig, Module
from woob.tools.value import ValueBackendPassword

from .browser import Ideel

__all__ = ['IdeelModule']


class IdeelModule(Module, CapShop):
    NAME = 'ideel'
    MAINTAINER = u'Oleg Plakhotniuk'
    EMAIL = 'olegus8@gmail.com'
    VERSION = '3.3'
    LICENSE = 'AGPLv3+'
    DESCRIPTION = u'Ideel'
    CONFIG = BackendConfig(
        ValueBackendPassword('username', label='User name', masked=False),
        ValueBackendPassword('password', label='Password'))
    BROWSER = Ideel

    def create_default_browser(self):
        return self.create_browser(self.config['username'].get(),
                                   self.config['password'].get())

    def get_currency(self):
        return self.browser.get_currency()

    def get_order(self, id_):
        return self.browser.get_order(id_)

    def iter_orders(self):
        return self.browser.iter_orders()

    def iter_payments(self, order):
        return self.browser.iter_payments(order)

    def iter_items(self, order):
        return self.browser.iter_items(order)
