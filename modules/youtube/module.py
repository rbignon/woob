# -*- coding: utf-8 -*-

# Copyright(C) 2010-2021 Christophe Benz, Romain Bignon
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

from woob.capabilities.base import empty
from woob.capabilities.image import Thumbnail
from woob.capabilities.video import CapVideo, BaseVideo
from woob.tools.backend import Module
from woob.tools.capabilities.video.ytdl import video_info

from .browser import YoutubeBrowser


__all__ = ['YoutubeModule']


class YoutubeModule(Module, CapVideo):
    NAME = 'youtube'
    MAINTAINER = u'Vincent A'
    EMAIL = 'dev@indigo.re'
    VERSION = '3.2'
    DESCRIPTION = 'YouTube video streaming website'
    LICENSE = 'LGPLv3+'
    BROWSER = YoutubeBrowser

    def _set_video_attrs(self, video):
        new_video = video_info(self.browser.video.build(id=video.id))
        if not new_video:
            return

        for k, v in new_video.iter_fields():
            if not empty(v) and empty(getattr(video, k)):
                setattr(video, k, v)

    def search_videos(self, pattern, sortby=CapVideo.SEARCH_RELEVANCE, nsfw=False):
        return self.browser.search_videos(pattern, sortby)

    def get_video(self, id_or_url):
        if "/" not in id_or_url:
            id_or_url = self.browser.video.build(id=id_or_url)
        return video_info(id_or_url)

    def fill_video(self, video, fields):
        if 'thumbnail' in fields and video.thumbnail:
            video.thumbnail.data = self.browser.open(video.thumbnail.url).content
        if 'url' in fields:
            self._set_video_attrs(video)
        return video

    def fill_thumb(self, thumb, fields):
        if 'data' in fields:
            thumb.data = self.browser.open(thumb.url).content

    OBJECTS = {
        BaseVideo: fill_video,
        Thumbnail: fill_thumb,
    }
