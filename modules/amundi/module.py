# Copyright(C) 2016      James GALT

# flake8: compatible
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


from woob.capabilities.bank.wealth import CapBankWealth
from woob.tools.backend import BackendConfig, Module
from woob.tools.value import Value, ValueBackendPassword, ValueTransient

from .browser import CAAmundi, EEAmundi, ESAmundi, TCAmundi


__all__ = ["AmundiModule"]


class AmundiModule(Module, CapBankWealth):
    NAME = "amundi"
    DESCRIPTION = "Amundi"
    MAINTAINER = "James GALT"
    EMAIL = "james.galt.bi@gmail.com"
    LICENSE = "LGPLv3+"
    VERSION = "3.7"
    CONFIG = BackendConfig(
        ValueBackendPassword("login", label="Identifiant", regexp=r"\d+", masked=False),
        ValueBackendPassword("password", label="Mot de passe"),
        ValueTransient("captcha_response"),
        ValueTransient("request_information"),
        ValueTransient("resume"),
        Value(
            "website",
            label="Type de compte",
            default="ee",
            choices={
                "ee": "Amundi Epargne Entreprise",
                "tc": "Amundi Tenue de Compte",
                "ca": "Amundi Crédit Agricole Assurances",
                "es": "Amundi Employee Shareholdings",
            },
        ),
    )

    def create_default_browser(self):
        browsers = {
            "ee": EEAmundi,
            "tc": TCAmundi,
            "ca": CAAmundi,
            "es": ESAmundi,
        }
        self.BROWSER = browsers[self.config["website"].get()]
        return self.create_browser(self.config, self.config["login"].get(), self.config["password"].get())

    def iter_accounts(self):
        return self.browser.iter_accounts()

    def iter_investment(self, account):
        for inv in self.browser.iter_investment(account):
            if inv.valuation != 0:
                yield inv

    def iter_pocket(self, account):
        return self.browser.iter_pockets(account)

    def iter_history(self, account):
        return self.browser.iter_history(account)
