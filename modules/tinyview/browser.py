# -*- coding: utf-8 -*-

# Copyright(C) 2021 Vincent A
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

from woob.browser import PagesBrowser, URL
from woob.browser.url import BrowserParamURL

from .pages import (
    EntriesPage, EntryPage,
)


class TinyViewBrowser(PagesBrowser):
    BASEURL = "https://storage.googleapis.com/"

    entries = BrowserParamURL(
        r"/tinyview-d78fb.appspot.com/(?P<browser_comic>[^?/]+)/index.json",
        EntriesPage
    )
    entry = URL(
        r"/tinyview-d78fb.appspot.com/(?P<id>.+)/index.json",
        EntryPage
    )
    # id is formatted like this: <browser_comic>/<year>/<month>/<day>/<slug>

    entry_image = BrowserParamURL(r"/tinyview-d78fb.appspot.com/(?P<browser_comic>[^?/]+)/(?P<y>\d{4})/(?P<m>\d{2})/(?P<d>\d{2})/(?P<slug>[^?/]+)/(?P<filename>[^?/]+)")
    base_storage = URL(r"/tinyview-d78fb.appspot.com/(?P<rest>)")

    user_page = URL("https://tinyview.com/(?P<page>.+)")

    def __init__(self, comic, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.comic = comic

    def get_entry(self, id):
        self.entry.go(id=id)
        return self.page.get_entry()

    def iter_entries(self):
        self.entries.go()
        return self.page.iter_entries()
