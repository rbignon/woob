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

from woob.capabilities.bank import CapBankTransferAddRecipient
from woob.capabilities.bank.wealth import CapBankWealth
from woob.capabilities.messages import CapMessages
from woob.capabilities.contact import CapContact
from woob.capabilities.profile import CapProfile
from woob.tools.backend import AbstractModule
from woob.capabilities.bill import CapDocument


__all__ = ['BNPorcModule']


class BNPorcModule(
    AbstractModule, CapBankWealth, CapBankTransferAddRecipient, CapMessages, CapContact, CapProfile, CapDocument
):
    NAME = 'bnporc'
    MAINTAINER = u'Romain Bignon'
    EMAIL = 'romain@weboob.org'
    VERSION = '3.4'
    DEPENDENCIES = ('bnp',)
    LICENSE = 'LGPLv3+'
    DESCRIPTION = 'BNP Paribas'
    PARENT = 'bnp'
