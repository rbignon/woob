# -*- coding: utf-8 -*-

# Copyright(C) 2010-2011 Romain Bignon
# Copyright(C) 2012 François Revol
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

from woob.capabilities.video import CapVideo, BaseVideo
from woob.tools.backend import Module
from woob.tools.capabilities.video.ytdl import video_info


from .browser import VimeoBrowser


__all__ = ['VimeoModule']


class VimeoModule(Module, CapVideo):
    NAME = 'vimeo'
    MAINTAINER = u'François Revol'
    EMAIL = 'revol@free.fr'
    VERSION = '3.3'
    DESCRIPTION = 'Vimeo video streaming website'
    LICENSE = 'AGPLv3+'
    BROWSER = VimeoBrowser

    def search_videos(self, pattern, sortby=CapVideo.SEARCH_RELEVANCE, nsfw=False):
        return self.browser.search_videos(pattern, sortby, nsfw)

    def fill_video(self, video, fields):
        if fields != ['thumbnail']:
            # if we don't want only the thumbnail, we probably want also every fields
            video = video_info(self.browser.absurl('/%s' % video.id, base=True))

        if 'thumbnail' in fields and video and video.thumbnail:
            video.thumbnail.data = self.browser.open(video.thumbnail.url).content

        return video

    OBJECTS = {BaseVideo: fill_video}
