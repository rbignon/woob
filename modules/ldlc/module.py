# Copyright(C) 2015      Vincent Paredes
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

from woob.capabilities.bill import CapDocument, Bill
from woob.capabilities.base import empty
from woob.tools.value import Value
from woob_modules.materielnet.module import MaterielnetModule

from .browser import LdlcParBrowser, LdlcProBrowser


__all__ = ['LdlcModule']


class LdlcModule(MaterielnetModule, CapDocument):
    NAME = 'ldlc'
    DESCRIPTION = 'ldlc website'
    MAINTAINER = 'Vincent Paredes'
    EMAIL = 'vparedes@budget-insight.com'
    LICENSE = 'LGPLv3+'
    VERSION = '3.6'
    DEPENDENCIES = ('materielnet',)
    CONFIG = MaterielnetModule.CONFIG.with_values(
        Value('website', label='Site web', default='part', choices={'pro': 'Professionnels', 'part': 'Particuliers'}),
    )

    def create_default_browser(self):
        if self.config['website'].get() == 'part':
            self.BROWSER = LdlcParBrowser
            return self.create_browser(
                self.config,
                self.config['login'].get(),
                self.config['password'].get(),
            )
        else:
            self.BROWSER = LdlcProBrowser
            return self.create_browser(self.config, self.config['login'].get(), self.config['password'].get())

    def download_document(self, bill):
        if not isinstance(bill, Bill):
            bill = self.get_document(bill)
        if empty(bill.url):
            return
        return self.browser.open(bill.url).content
