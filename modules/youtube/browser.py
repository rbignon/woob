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

from woob.browser import URL, PagesBrowser

from .pages import ResultsPage


class YoutubeBrowser(PagesBrowser):
    BASEURL = "https://www.youtube.com/"

    search = URL(r"/results", ResultsPage)
    video = URL(r"/watch\?v=(?P<id>[^&]+)")

    def search_videos(self, pattern, sortby):
        self.search.go(params={"search_query": pattern})
        return self.page.iter_videos()
