# -*- coding: utf-8 -*-

# Copyright(C) 2012-2021  Budget Insight
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


from weboob.tools.backend import AbstractModule, BackendConfig
from weboob.tools.value import Value, ValueBackendPassword
from weboob.capabilities.bank import CapBank

from .browser import GanpatrimoineBrowser


__all__ = ['GanpatrimoineModule']


class GanpatrimoineModule(AbstractModule, CapBank):
    NAME = 'ganpatrimoine'
    DESCRIPTION = u'Gan Patrimoine'
    MAINTAINER = u'Jean Walrave'
    EMAIL = 'jwalrave@budget-insight.com'
    LICENSE = 'LGPLv3+'
    VERSION = '1.3'

    CONFIG = BackendConfig(Value('website', label='Banque', default='espaceclient.ganpatrimoine.fr'),
                           ValueBackendPassword('login',    label=u'Numéro client', masked=False),
                           ValueBackendPassword('password', label=u"Code d'accès"))

    PARENT = "ganassurances"
    BROWSER = GanpatrimoineBrowser

    def create_default_browser(self):
        return self.create_browser(self.weboob, self.config['website'].get(), self.config['login'].get(), self.config['password'].get())
