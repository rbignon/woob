# -*- coding: utf-8 -*-

# Copyright(C) 2010-2011 Christophe Benz
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

from .pages import MediaPage, PlayerPage, SearchPage


__all__ = ['InaBrowser']


class InaBrowser(PagesBrowser):
    BASEURL = 'https://www.ina.fr/'

    search_page = URL(
        '/ajax/recherche\?q=(?P<pattern>.*)&espace=1&media=(?P<type>(2|3))&sort=pertinence&order=desc&offset=(?P<first_item>\d+)',
        SearchPage)
    video_page = URL('/ina-eclaire-actu/video/(?P<id>.*)/.*$', MediaPage)
    audio_page = URL('/ina-eclaire-actu/audio/(?P<id>.*)/.*$', MediaPage)
    json_player_page = URL('https://apipartner.ina.fr/assets/(?P<id>.*)?sign=(?P<sign>.*)&partnerId=2', PlayerPage)

    @video_page.id2url
    def get_video(self, url, video=None):
        self.location(url)
        assert self.video_page.is_here()

        self.session.headers['Accept'] = '*/*'

        self.location(self.page.get_player_url())
        assert self.json_player_page.is_here()

        video = self.page.get_audio(obj=video)
        return video

    def search_videos(self, pattern):
        return self.search_page.go(pattern=pattern.encode('utf-8'),
                                   type='2',
                                   first_item='0').iter_videos()

    @audio_page.id2url
    def get_audio(self, url, audio=None):
        self.location(url)
        assert self.audio_page.is_here()

        self.session.headers['Accept'] = '*/*'

        self.location(self.page.get_player_url())
        assert self.json_player_page.is_here()

        audio = self.page.get_audio(obj=audio)
        return audio

    def search_audio(self, pattern):
        return self.search_page.go(pattern=pattern.encode('utf-8'),
                                   type='3',
                                   first_item='0').iter_audios()
