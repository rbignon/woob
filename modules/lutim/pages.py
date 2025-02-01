# -*- coding: utf-8 -*-

# Copyright(C) 2015      Vincent A
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

# flake8: compatible

import re

from woob.browser.pages import JsonPage, RawPage
from woob.capabilities.base import UserError


class ImagePage(RawPage):
    @property
    def contents(self):
        return self.doc

    @property
    def filename(self):
        header = self.response.headers["content-disposition"]
        m = re.match('inline;filename="(.*)"', header)
        return m.group(1)


class UploadPage(JsonPage):
    def fetch_info(self):
        if not self.doc["success"]:
            raise UserError(self.doc["msg"]["msg"])

        return self.doc["msg"]
