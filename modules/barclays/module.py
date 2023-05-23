# -*- coding: utf-8 -*-

# Copyright(C) 2010-2016 Romain Bignon
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
from woob.capabilities.profile import CapProfile
from woob.tools.backend import AbstractModule


__all__ = ['BarclaysModule']


class BarclaysModule(AbstractModule, CapBankWealth, CapProfile):
    NAME = 'barclays'
    MAINTAINER = u'Romain Bignon'
    EMAIL = 'romain@weboob.org'
    VERSION = '3.6'
    DEPENDENCIES = ('milleis',)
    LICENSE = 'LGPLv3+'
    DESCRIPTION = 'Milleis'
    PARENT = 'milleis'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger.warning("'barclays' module is deprecated and should be replaced by 'milleis'")
