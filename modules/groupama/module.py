# Copyright(C) 2023 Powens
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
from woob_modules.ganpatrimoine import GanPatrimoineModule

from .browser import GroupamaBrowser


__all__ = ['GroupamaModule']


class GroupamaModule(GanPatrimoineModule, CapBank):
    NAME = 'groupama'
    DESCRIPTION = 'Groupama'
    MAINTAINER = 'Quentin Defenouillere'
    EMAIL = 'quentin.defenouillere@budget-insight.com'
    LICENSE = 'LGPLv3+'
    VERSION = '3.5'
    DEPENDENCIES = ('ganpatrimoine',)

    BROWSER = GroupamaBrowser

    def create_default_browser(self):
        return self.create_browser(
            'groupama',
            self.config,
            self.config['login'].get(),
            self.config['password'].get(),
            woob=self.woob
        )
