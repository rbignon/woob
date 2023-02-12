# -*- coding: utf-8 -*-

# Copyright(C) 2021 Damien Ramelet
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

from woob.tools.value import ValueBackendPassword
from woob.tools.backend import BackendConfig, Module
from woob.capabilities.bank.transfer import CapBankTransferAddRecipient

from .browser import HeliosBrowser


__all__ = ['HeliosModule']


class HeliosModule(Module, CapBankTransferAddRecipient):
    NAME = 'helios'
    DESCRIPTION = 'Helios is a neobank which excludes fossil fuels from its investments.'
    MAINTAINER = 'Damien Ramelet'
    EMAIL = 'damien.ramelet@protonmail.com'
    LICENSE = 'LGPLv3+'
    VERSION = '3.3.1'

    BROWSER = HeliosBrowser

    CONFIG = BackendConfig(
        ValueBackendPassword('login', label='Adresse e-mail', masked=False, regexp=r'.+@.+'),
        ValueBackendPassword('password', label='Code secret', regexp=r'\d{6}'),
    )

    def create_default_browser(self):
        return self.create_browser(
            self.config['login'].get(), self.config['password'].get()
        )

    def iter_accounts(self):
        return self.browser.iter_accounts()

    def iter_history(self, account):
        return self.browser.iter_history(account)

    def iter_transfer_recipients(self, account):
        return self.browser.iter_recipients(account)

    def new_recipient(self, recipient, **kwargs):
        return self.browser.new_recipient(recipient, **kwargs)

    def init_transfer(self, transfer, **kwargs):
        if self.browser.has_transfer_in_progress(transfer, **kwargs):
            # Now that it has been initiated, it has to be executed
            return transfer
        return self.browser.init_transfer(transfer, **kwargs)

    def execute_transfer(self, transfer, **params):
        return self.browser.execute_transfer(transfer, **params)
