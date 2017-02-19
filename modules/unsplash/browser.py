# -*- coding: utf-8 -*-

# Copyright(C) 2017      Vincent A
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

from weboob.browser import PagesBrowser, URL

from .pages import ImageSearch


class UnsplashBrowser(PagesBrowser):
    BASEURL = 'https://unsplash.com'

    collection_search = URL(r'/napi/search/collections\?query=(?P<term>[^&]+)&page=(?P<page>\d+)&per_page=20')
    image_search = URL(r'/napi/search/photos\?query=(?P<term>[^&]+)&page=(?P<page>\d+)&per_page=20', ImageSearch)

    def __init__(self, *args, **kwargs):
        super(UnsplashBrowser, self).__init__(*args, **kwargs)
        self.session.headers['Authorization'] = 'Client-ID d69927c7ea5c770fa2ce9a2f1e3589bd896454f7068f689d8e41a25b54fa6042'

    def search_image(self, term):
        n = 1
        nb_pages = 1
        while n <= nb_pages:
            self.image_search.go(term=term, page=n)
            for img in self.page.iter_images():
                yield img
            nb_pages = self.page.nb_pages()
            n += 1
