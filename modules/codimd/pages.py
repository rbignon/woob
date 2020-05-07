# -*- coding: utf-8 -*-

# Copyright(C) 2012-2020  Budget Insight
#
# This file is part of a weboob module.
#
# This weboob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This weboob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this weboob module. If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

import re
from urllib.parse import unquote

from weboob.browser.pages import RawPage, JsonPage, HTMLPage
from weboob.browser.filters.standard import CleanText
from weboob.exceptions import BrowserIncorrectPassword


class RootPage(HTMLPage):
    def requires_auth(self):
        return 'try logging' in self.get_error()

    def get_error(self):
        return CleanText('//div[has-class("alert")]')(self.doc)

    def check_error(self):
        msg = self.get_error()
        if 'Invalid' in msg:
            raise BrowserIncorrectPassword()
        elif msg:
            raise AssertionError('%r is not handled' % msg)


class NotePage(RawPage):
    def get_title(self):
        return unquote(
            re.search(
                r'filename=(?P<q>"?)(?P<name>.*?)(?P=q)',
                self.response.headers['Content-Disposition']
            )['name']
        )


class MePage(JsonPage):
    pass


class RevisionListPage(JsonPage):
    def get_list(self):
        return [r['time'] for r in self.doc['revision']]


class RevisionPage(JsonPage):
    def get_content(self):
        return self.doc['content']


class NewNotePage(RawPage):
    pass
