# Copyright(C) 2017      Vincent A
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

from woob.browser import URL, PagesBrowser

from .pages import CatchHTTP, EntryPage, ListPage, SearchPage


class RedditBrowser(PagesBrowser):
    BASEURL = "https://www.reddit.com/r/pics/"

    listing = URL(r"(?P<cat>\w*)/?\?count=\d+&after=(?P<after>\w+)", r"(?P<cat>\w*)/?$", ListPage)
    entry = URL(r"/comments/(?P<id>\w+)/.*", EntryPage)
    search = URL(r"search\?sort=(?P<sort>\w+)&restrict_sr=on", SearchPage)
    # catch-all to avoid BrowserHTTPSDowngrade
    catch_http = URL(r"http://.*", CatchHTTP)

    def __init__(self, sub, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.BASEURL = "https://www.reddit.com/r/%s/" % sub

    def iter_images(self, cat=""):
        self.listing.go(cat=cat)
        return self.page.iter_images()

    def search_images(self, pattern, sort="top", nsfw=False):
        nsfw = {True: "yes", False: "no"}[nsfw]
        pattern = f"{pattern} nsfw:{nsfw}"

        self.search.go(sort=sort, params={"q": pattern})
        return self.page.iter_images()

    def iter_threads(self, cat=""):
        self.listing.go(cat=cat)
        return self.page.iter_threads()

    def fill_thread(self, thread):
        self.location(thread.url, params={"sort": "old"})
        assert self.entry.is_here()
        self.page.fill_thread(thread)

    def get_thread(self, id):
        self.entry.go(id=id, params={"sort": "old"})
        return self.page.get_thread(id)

    def get_image(self, id):
        self.entry.go(id=id)
        img = self.page.get_image()
        img.id = id
        return img
