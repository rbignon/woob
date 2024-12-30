# -*- coding: utf-8 -*-

# Copyright(C) 2017      Roger Philibert
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

from .pages import SearchPage, VideoPage


class XHamsterBrowser(PagesBrowser):
    BASEURL = 'https://fr.xhamster.com'

    video = URL(r'/videos/(?P<id>.+)', VideoPage)
    search = URL(r'/search\?q=(?P<pattern>[^&]+)', SearchPage)

    def do_search(self, pattern):
        self.location('/search', params={'q': pattern})
        return self.page.iter_videos()

    def get_video(self, _id):
        self.video.go(id=_id)
        return self.page.get_video()
