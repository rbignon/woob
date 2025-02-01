# Copyright(C) 2013 Julien Veyssier
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

from .pages import SearchPage, SubtitlePage


__all__ = ["PodnapisiBrowser"]


class PodnapisiBrowser(PagesBrowser):
    BASEURL = "https://www.podnapisi.net"
    search = URL(
        r"/subtitles/search/advanced\?keywords=(?P<keywords>.*)&language=(?P<language>.*)",
        r"/en/subtitles/search/advanced\?keywords=(?P<keywords>.*)&language=(?P<language>.*)",
        SearchPage,
    )
    file = URL(r"/subtitles/(?P<id>-*\w*)/download")
    subtitle = URL(r"/subtitles/(?P<id>.*)", SubtitlePage)

    def iter_subtitles(self, language, pattern):
        return self.search.go(language=language, keywords=pattern).iter_subtitles()

    def get_file(self, id):
        return self.file.go(id=id).content

    def get_subtitle(self, id):
        return self.subtitle.go(id=id).get_subtitle()
