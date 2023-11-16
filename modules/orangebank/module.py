# Copyright(C) 2018-2023 Powens
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

from woob.tools.backend import Module, BackendConfig
from woob.capabilities.bank.transfer import (
    CapBankTransferAddRecipient, TransferDateType,
)
from woob.capabilities.profile import CapProfile
from woob.tools.value import ValueBackendPassword, ValueTransient

from .browser import OrangeBankBrowser

__all__ = ['OrangeBankModule']


class OrangeBankModule(Module, CapBankTransferAddRecipient, CapProfile):
    NAME = 'orangebank'
    DESCRIPTION = 'Orange Bank'
    MAINTAINER = 'Powens'
    EMAIL = 'dev@powens.com'
    LICENSE = 'LGPLv3+'
    VERSION = '3.6'

    BROWSER = OrangeBankBrowser

    CONFIG = BackendConfig(
        ValueBackendPassword(
            'login',
            label='Identifiant',
            regexp=r'^[0-9]{8}$',
            masked=False,
            required=True,
        ),
        ValueTransient('captcha_response'),
        ValueTransient('resume'),
        ValueTransient('request_information'),
    )

    accepted_execution_date_types = (TransferDateType.FIRST_OPEN_DAY,)

    def create_default_browser(self):
        return self.create_browser(self.config)

    def iter_accounts(self):
        return self.browser.iter_accounts()

    def iter_history(self, account):
        return self.browser.iter_history(account)

    def iter_coming(self, account):
        raise NotImplementedError  # TODO

    def get_profile(self):
        return self.browser.get_profile()

    def init_transfer(self, transfer, **params):
        return self.browser.init_transfer(transfer, **params)

    def execute_transfer(self, transfer, **params):
        return self.browser.execute_transfer(transfer, **params)

    def get_transfer(self, id):
        return self.browser.get_transfer(id)

    def iter_transfer_recipients(self, account):
        return self.browser.iter_transfer_recipients(account)

    def new_recipient(self, recipient, **params):
        return self.browser.new_recipient(recipient, **params)

    def transfer_check_exec_date(self, old_date, new_date):
        # Since init_transfer does not actually create any resource,
        # and sometimes modifies the date, there is no anomalous changing
        # of the date and, therefore, no need to check if it has changed here.
        return True
