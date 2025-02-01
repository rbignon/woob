# flake8: compatible

# Copyright(C) 2023     Budget Insight
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

from woob.browser.filters.json import Dict
from woob.browser.filters.standard import CleanDecimal, Type
from woob.browser.pages import JsonPage


__all__ = ["BalancePage", "CaptchaPage"]


class CaptchaPage(JsonPage):
    def get_status(self):
        return Type(Dict("status")(self.doc), type=int)(self.doc)

    def get_response(self):
        return Dict("request")(self.doc)


class BalancePage(JsonPage):
    def get_balance(self):
        return CleanDecimal.SI(Dict("request"))(self.doc)
