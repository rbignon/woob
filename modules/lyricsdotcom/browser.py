# Copyright(C) 2016 Julien Veyssier
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
from woob.browser.profiles import Firefox
from woob.browser.url import URL

from .pages import ArtistPages, LyricsPage, SearchPage


__all__ = ["LyricsdotcomBrowser"]


class LyricsdotcomBrowser(PagesBrowser):
    PROFILE = Firefox()
    TIMEOUT = 30

    BASEURL = "http://www.lyrics.com"
    search = URL(r"/serp\.php\?st=(?P<pattern>.*)&qtype=(?P<criteria>1|2)", SearchPage)
    songLyrics = URL(r"/lyric/(?P<id>\d*)", LyricsPage)
    artistsong = URL(r"/artist/(?P<id>.*)", ArtistPages)

    def iter_lyrics(self, criteria, pattern):
        if criteria == "song":
            self.search.go(pattern=pattern, criteria=1)
            assert self.search.is_here()
            yield from self.page.iter_lyrics()
        elif criteria == "artist":
            self.search.go(pattern=pattern, criteria=2)
            assert self.search.is_here()
            for artist in self.page.iter_artists():
                yield from self.artistsong.go(id=artist.id).iter_lyrics()

    def get_lyrics(self, id):
        return self.songLyrics.go(id=id).get_lyrics()
