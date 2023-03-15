# Copyright(C) 2013-2023 Romain Bignon
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
from woob.tools.backend import AbstractModule, BackendConfig
from woob.tools.value import ValueBackendPassword


__all__ = ['BanqueAccordModule']


class BanqueAccordModule(AbstractModule, CapBank):
    NAME = 'banqueaccord'
    DESCRIPTION = u'Banque Accord'
    MAINTAINER = u'Romain Bignon'
    EMAIL = 'romain@weboob.org'
    LICENSE = 'LGPLv3+'
    VERSION = '3.4'
    DEPENDENCIES = ('oney',)
    CONFIG = BackendConfig(ValueBackendPassword('login',    label='Identifiant', regexp='\d+', masked=False),
                           ValueBackendPassword('password', label=u"Code d'accès", regexp='\d+'))

    PARENT = 'oney'
