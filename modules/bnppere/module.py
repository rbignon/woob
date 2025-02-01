# Copyright(C) 2016      Edouard Lambert
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
from woob.capabilities.bill import CapDocument
from woob.capabilities.profile import CapProfile
from woob.tools.backend import BackendConfig
from woob.tools.value import Value, ValueBackendPassword, ValueTransient
from woob_modules.s2e.module import S2eModule

from .browser import BnppereBrowser, VisiogoBrowser


__all__ = ["BnppereModule"]


class BnppereModule(S2eModule, CapBankWealth, CapDocument, CapProfile):
    NAME = "bnppere"
    DESCRIPTION = "BNP Épargne Salariale"
    MAINTAINER = "Edouard Lambert"
    EMAIL = "elambert@budget-insight.com"
    LICENSE = "LGPLv3+"
    VERSION = "3.7"
    DEPENDENCIES = ("s2e",)

    CONFIG = BackendConfig(
        ValueBackendPassword("login", label="Identifiant", masked=False),
        ValueBackendPassword("password", label="Code secret"),
        Value("otp", label="Code de sécurité", default="", regexp=r"^(\d{6})$"),
        ValueTransient("request_information"),
        Value(
            "website",
            label="Espace Client",
            default="personeo",
            choices={
                "personeo": "PEE, PERCO (Personeo)",
                "visiogo": "PER Entreprises (Visiogo)",
            },
        ),
    )

    def create_default_browser(self):
        websites = {
            "personeo": BnppereBrowser,
            "visiogo": VisiogoBrowser,
        }
        self.BROWSER = websites[self.config["website"].get()]
        return self.create_browser(self.config)

    def iter_accounts(self):
        return self.browser.iter_accounts()

    def iter_history(self, account):
        return self.browser.iter_history(account)

    def get_profile(self):
        return self.browser.get_profile()

    def iter_subscription(self):
        website = self.config["website"].get()
        if website == "visiogo":
            raise NotImplementedError()
        return super(BnppereModule, self).iter_subscription()
