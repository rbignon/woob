# Copyright(C) 2014      Bezleputh
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

from woob.capabilities.bank.wealth import CapBankWealth
from woob_modules.cmes.module import CmesModule

from .browser import GroupamaesBrowser


__all__ = ['GroupamaesModule']


class GroupamaesModule(CmesModule, CapBankWealth):
    NAME = 'groupamaes'
    DESCRIPTION = 'Groupama Épargne Salariale'
    MAINTAINER = 'Bezleputh'
    EMAIL = 'carton_ben@yahoo.fr'
    LICENSE = 'LGPLv3+'
    VERSION = '3.5'
    DEPENDENCIES = ('cmes',)

    BROWSER = GroupamaesBrowser

    def create_default_browser(self):
        return self.create_browser(
            self.config,
            self.config['login'].get(),
            self.config['password'].get(),
            'https://www.gestion-epargne-salariale.fr',
            'groupama-es/',
        )
