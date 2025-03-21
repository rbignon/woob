# Copyright(C) 2017      Théo Dorée
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

from woob.capabilities.bank import Account, CapBank
from woob.tools.backend import BackendConfig, Module
from woob.tools.value import ValueBackendPassword, ValueTransient

from .browser import MyedenredBrowser


__all__ = ["MyedenredModule"]


class MyedenredModule(Module, CapBank):
    NAME = "myedenred"
    DESCRIPTION = "MyEdenRed"
    MAINTAINER = "Théo Dorée"
    EMAIL = "tdoree@budget-insight.com"
    LICENSE = "LGPLv3+"
    VERSION = "3.7"
    CONFIG = BackendConfig(
        ValueBackendPassword("login", label="Adresse email", masked=False, regexp=r"[^@]{1,}@([^\.]{1,}\.)+\S{2,}$"),
        ValueBackendPassword("password", label="Mot de passe"),
        ValueTransient("captcha_response", label="Captcha Response"),
    )

    BROWSER = MyedenredBrowser

    def create_default_browser(self):
        return self.create_browser(self.config)

    def iter_accounts(self):
        return self.browser.iter_accounts()

    def iter_history(self, account):
        if not isinstance(account, Account):
            account = self.get_account(account)
        return self.browser.iter_history(account)
