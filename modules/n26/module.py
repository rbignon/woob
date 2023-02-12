# -*- coding: utf-8 -*-

# Copyright(C) 2016      Benjamin Bouvier
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
from woob.tools.backend import Module, BackendConfig
from woob.tools.value import Value, ValueBackendPassword, ValueTransient

from .browser import Number26Browser

__all__ = ['Number26Module']


class Number26Module(Module, CapBank):
    NAME = 'n26'
    DESCRIPTION = 'Bank N26'
    MAINTAINER = 'Stéphane SOBUCKI'
    EMAIL = 'stephane.sobucki@budget-insight.com'
    LICENSE = 'LGPLv3+'
    VERSION = '3.3'

    BROWSER = Number26Browser

    CONFIG = BackendConfig(
        Value('login', label='Email', regexp='.+'),
        ValueBackendPassword('password', label='Password'),
        ValueTransient('otp'),
        ValueTransient('resume'),
        ValueTransient('request_information')
    )

    STORAGE = {'categories': {}}

    def get_categories(self):
        categories = self.storage.get('categories')
        if not categories:
            categories = self.browser.get_categories()
            self.storage.set('categories', categories)
        return categories

    def create_default_browser(self):
        return self.create_browser(self.config)

    def iter_accounts(self):
        return self.browser.iter_accounts()

    def get_account(self, id):
        return self.browser.get_account(id)

    def iter_history(self, account):
        categories = self.get_categories()
        return self.browser.iter_history(categories=categories)

    def iter_coming(self, account):
        categories = self.get_categories()
        return self.browser.iter_coming(categories=categories)
