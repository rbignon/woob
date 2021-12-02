# -*- coding: utf-8 -*-

# Copyright(C) 2010-2011 Julien Veyssier
# Copyright(C) 2012-2013 Romain Bignon
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

from woob.capabilities.bank import CapBankTransferAddRecipient
from woob.capabilities.contact import CapContact
from woob_modules.creditmutuel.module import CreditMutuelModule

from .browser import BECMBrowser


__all__ = ['BECMModule']


class BECMModule(CreditMutuelModule, CapBankTransferAddRecipient, CapContact):
    NAME = 'becm'
    MAINTAINER = u'Victor Kannemacher'
    EMAIL = 'vkannemacher.budgetinsight@gmail.com'
    VERSION = '3.1'
    DEPENDENCIES = ('creditmutuel',)
    DESCRIPTION = u'Banque Européenne Crédit Mutuel'
    LICENSE = 'LGPLv3+'

    BROWSER = BECMBrowser

    def create_default_browser(self):
        browser = self.create_browser(self.config, weboob=self.weboob)
        browser.new_accounts.urls.insert(0, "/mabanque/fr/banque/comptes-et-contrats.html")
        return browser
