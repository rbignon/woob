# -*- coding: utf-8 -*-

# Copyright(C) 2010-2016 Julien Veyssier
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


from woob.browser import PagesBrowser
from woob.browser.exceptions import BrowserHTTPNotFound
from woob.browser.profiles import Firefox
from woob.browser.url import URL

from .pages import SearchPage, TorrentPage


__all__ = ['KickassBrowser']


class KickassBrowser(PagesBrowser):
    PROFILE = Firefox()
    TIMEOUT = 30

    BASEURL = 'https://kat.cr/'
    search = URL(r'usearch/(?P<pattern>.*)/\?field=seeders&sorder=desc',
                 SearchPage)
    torrent = URL(r'torrent-t(?P<id>.*)\.html',
                  r'.*-t[0-9]*\.html',
                  TorrentPage)

    def iter_torrents(self, pattern):
        self.search.go(pattern=pattern)
        #print( self.page.content)
        return self.page.iter_torrents()

    def get_torrent(self, fullid):
        try:
            self.torrent.go(id=fullid)
            torrent = self.page.get_torrent()
            return torrent
        except BrowserHTTPNotFound:
            return
