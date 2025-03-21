# Copyright(C) 2018 Arthur Huillet
#
# This file is part of a woob module.
#
# This woob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This woob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this woob module. If not, see <http://www.gnu.org/licenses/>.


from woob.capabilities.bank import AccountNotFound, CapBankWealth
from woob.capabilities.base import find_object
from woob.tools.backend import BackendConfig, Module
from woob.tools.value import ValueBackendPassword

from .browser import Suravenir


__all__ = ["SuravenirModule"]


class SuravenirModule(Module, CapBankWealth):
    NAME = "suravenir"
    MAINTAINER = "Arthur Huillet"
    EMAIL = "arthur.huillet+weboob@free.fr"
    VERSION = "3.7"
    LICENSE = "AGPLv3+"
    DESCRIPTION = "Assurance-vie Suravenir à travers différents courtiers (assurancevie.com, linxea, ...)"
    CONFIG = BackendConfig(
        ValueBackendPassword(
            "broker", label="Courtier", choices=Suravenir.broker_to_instance.keys(), masked=False, required=True
        ),
        ValueBackendPassword("login", label="Identifiant", masked=False, required=True),
        ValueBackendPassword("password", label="Mot de passe", required=True),
    )
    BROWSER = Suravenir

    def create_default_browser(self):
        return self.create_browser(
            self.config["broker"].get(), self.config["login"].get(), self.config["password"].get()
        )

    def get_account(self, id):
        return find_object(self.iter_accounts(), id=id, error=AccountNotFound)

    def iter_accounts(self):
        return self.browser.get_accounts_list()

    def iter_coming(self, account):
        raise NotImplementedError()

    def iter_history(self, account):
        return self.browser.iter_history(account)

    def iter_investment(self, account):
        return self.browser.iter_investments(account)
