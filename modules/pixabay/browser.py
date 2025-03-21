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
from urllib.parse import quote_plus

from woob.browser import URL
from woob.browser.browsers import LoginBrowser, need_login
from woob.capabilities.image import CapImage
from woob.exceptions import BrowserIncorrectPassword

from .pages import AccountPage, LoginPage, SearchAPI, ViewPage


class PixabayBrowser(LoginBrowser):
    BASEURL = "https://pixabay.com"
    DEFAULT_KEY = "2182074-ee443567762485ef2d40b6275"

    SORTS = {
        CapImage.SEARCH_RELEVANCE: "popular",
        CapImage.SEARCH_RATING: "popular",
        CapImage.SEARCH_VIEWS: "popular",
        CapImage.SEARCH_DATE: "latest",
    }

    account_page = URL("/en/accounts/media/$", AccountPage)
    search_api = URL("/api/", SearchAPI)
    view_page = URL(r"/(?P<lang>[a-z]{2})/(?P<label>[\w-]+)-(?P<id>\d+)/$", ViewPage)
    dl_page = URL(r"/(?P<lang>[a-z]{2})/(?P<type>\w+)/download/(?P<filename>[\w.-]+$")
    login_page = URL(r"/(?P<lang>[a-z]{2})/accounts/login/$", LoginPage)

    def __init__(self, api_key=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.api_key = api_key or self.DEFAULT_KEY

    def _improve_low(self, d):
        # 960px is the largest size for the non-logged in
        d["webformatURL"] = re.sub(r"_\d+(\.[a-z]+)$", r"_960\1", d["webformatURL"])
        return d

    def search_images(self, pattern, sortby=CapImage.SEARCH_RELEVANCE, nsfw=False, **opts):
        opts["q"] = quote_plus(pattern)
        opts["order"] = self.SORTS[sortby]
        opts["safesearch"] = nsfw
        opts["key"] = self.api_key
        opts["per_page"] = 20
        opts["page"] = 1

        while True:
            self.search_api.go(params=opts)
            assert self.search_api.is_here()
            res = self.page.get()

            for d in res["hits"]:
                yield self._improve_low(d)

            if opts["page"] * opts["per_page"] >= res["totalHits"]:
                break
            opts["page"] += 1

    def get_image(self, _id):
        opts = {}
        opts["key"] = self.api_key
        opts["id"] = _id

        self.search_api.go(params=opts)
        assert self.search_api.is_here()
        d = self.page.get()
        if len(d["hits"]):
            return self._improve_low(d["hits"][0])
        else:
            return None

    @need_login
    def download_image(self, page_url):
        match = self.view_page.match(page_url)
        assert match
        self.view_page.go(**match.groupdict())
        assert self.view_page.is_here()

        params = {"lang": self.page.params["lang"], "type": self.page.type, "filename": self.page.filename}
        url = self.dl_page.build(**params)
        content = self.open(url).content
        return content

    def do_login(self):
        login = {}
        login["username"] = self.username
        login["password"] = self.password
        login["next"] = "/en/accounts/media/"
        self.login_page.go(lang="en", data=login)
        if self.login_page.is_here():
            raise BrowserIncorrectPassword()
        assert self.account_page.is_here()
