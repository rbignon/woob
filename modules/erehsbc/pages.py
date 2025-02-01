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

import re

from woob.browser.filters.json import Dict
from woob.browser.filters.standard import CleanText, Regexp
from woob.browser.pages import JsonPage, RawPage


class LoginPage(RawPage):
    pass


class AuthenticationPage(JsonPage):
    def get_password_json(self):
        return self.doc

    def get_public_key(self):
        return self.doc["header"][10:]

    def is_device_fingerprint_needed(self):
        return self.doc.get("stage") == "DeviceIdMatch2"

    def get_pre_otp_json(self):
        return self.doc

    def is_pre_otp_here(self):
        return self.doc["callbacks"][1]["output"][2]["value"][0] == "Send the code"

    def get_otp_json(self):
        return self.doc

    def is_wrong_otp(self):
        return self.doc["callbacks"] and "HotpReapp2" == self.doc["stage"]

    def is_json_to_trust_device(self):
        return re.search(
            "add to trusted devices|enregistrement de ce terminal",
            self.doc["callbacks"][0]["output"][0]["value"],
            re.IGNORECASE,
        )

    def get_email(self):
        return Regexp(CleanText(Dict("header", default="")), r"email=(.+),", default="")(self.doc)


class FinalizeAuthenticationPage(RawPage):
    pass
