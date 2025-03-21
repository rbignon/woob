# Copyright(C) 2016      Vincent A
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

import re

from woob.browser.pages import HTMLPage
from woob.tools.misc import get_bytes_size


class PageUpload(HTMLPage):
    def get_max_sizes(self):
        max_size = None
        for item in self.doc.getroot().xpath('//p[has-class("config")]'):
            if not item.text:
                continue
            match = re.search(r"File size is limited to (\d+) ([A-Za-z]+)", item.text)
            if match:
                max_size = int(get_bytes_size(int(match.group(1)), match.group(2)))
                break

        async_size = 16 * 1024 * 1024
        for item in self.doc.xpath("//script"):
            if not item.text:
                continue
            match = re.search(r"upload \(.*, (\d+)\)", item.text)
            if match:
                async_size = int(match.group(1))
                break

        self.logger.debug("max size = %s, max part size = %s", max_size, async_size)

        return max_size, async_size


class PageFile(HTMLPage):
    def has_error(self):
        return bool(self.doc.xpath('//*[has-class("error")]'))
