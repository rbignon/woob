# Copyright(C) 2012 Lucien Loiseau
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

import json
import re

from woob.browser.pages import RawPage
from woob.capabilities import NotAvailable


class TranslatePage(RawPage):

    def build_doc(self, content):
        encoding = self.encoding
        if encoding == "latin-1":
            encoding = "latin1"
        if encoding:
            encoding = encoding.replace("iso8859_", "iso8859-")

        return content.decode(encoding)

    def get_translation(self, result_handler):
        m = re.search(r"^(\[\[.*\]\]$)", self.doc, re.MULTILINE)
        if m:
            try:
                subdata = json.loads(json.loads(m.group(1))[0][2])
                subdata = result_handler(subdata)
                assert isinstance(subdata, str)
                return subdata
            except (IndexError, TypeError, ValueError):
                self.logger.warning("can't handle data %r", m.group(1))

        return NotAvailable


class SupportedLanguagesPage(RawPage):
    def build_doc(self, content):
        encoding = self.encoding
        if encoding == "latin-1":
            encoding = "latin1"
        if encoding:
            encoding = encoding.replace("iso8859_", "iso8859-")

        m = re.search(r".*({.*}).*", content.decode(encoding).replace("'", '"'))
        if m:
            return json.loads(m.group(1))
        return {}

    def get_supported_languages(self):
        return self.doc
