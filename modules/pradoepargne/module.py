# -*- coding: utf-8 -*-

# Copyright(C) 2017      Edouard Lambert
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

from woob.tools.backend import BackendConfig
from woob.tools.value import ValueBackendPassword
from woob.capabilities.bank.wealth import CapBankWealth
from woob_modules.humanis.module import HumanisModule


__all__ = ['PradoepargneModule']


class PradoepargneModule(HumanisModule, CapBankWealth):
    NAME = 'pradoepargne'
    DESCRIPTION = 'Prado Épargne Salariale'
    MAINTAINER = 'Edouard Lambert'
    EMAIL = 'elambert@budget-insight.com'
    LICENSE = 'LGPLv3+'
    VERSION = '3.3'
    DEPENDENCIES = ('humanis',)
    CONFIG = BackendConfig(
        *HumanisModule.CONFIG.values(),
        ValueBackendPassword('login', label='Identifiant', masked=False),
    )

    PARENT = 'humanis'
