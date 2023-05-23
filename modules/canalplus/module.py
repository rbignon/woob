# -*- coding: utf-8 -*-

# Copyright(C) 2010-2011 Nicolas Duhamel
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

from woob.capabilities.video import CapVideo, BaseVideo
from woob.tools.backend import Module, BackendConfig
from woob.tools.value import Value

from .browser import CanalplusBrowser
from .video import CanalplusVideo

from woob.capabilities.collection import CapCollection


__all__ = ['CanalplusModule']


class CanalplusModule(Module, CapVideo, CapCollection):
    NAME = 'canalplus'
    MAINTAINER = u'Nicolas Duhamel'
    EMAIL = 'nicolas@jombi.fr'
    VERSION = '3.6'
    DESCRIPTION = 'Canal Plus French TV'
    LICENSE = 'AGPLv3+'
    CONFIG = BackendConfig(Value('quality', label='Quality of videos', choices=['hd', 'sd'], default='hd'))
    BROWSER = CanalplusBrowser

    def create_default_browser(self):
        return self.create_browser(quality=self.config['quality'].get())

    def search_videos(self, pattern, sortby=CapVideo.SEARCH_RELEVANCE, nsfw=False):
        return self.browser.search_videos(pattern)

    def get_video(self, _id):
        m = re.match('https?://www\.canal-?plus\.fr/.*\?vid=(\d+)', _id)
        if m:
            _id = m.group(1)
        return self.browser.get_video(_id)

    def fill_video(self, video, fields):
        if fields != ['thumbnail']:
            # if we don't want only the thumbnail, we probably want also every fields
            video = self.browser.get_video(CanalplusVideo.id2url(video.id), video)
        if 'thumbnail' in fields and video.thumbnail:
            video.thumbnail.data = self.browser.open(video.thumbnail.url).content
        return video

    OBJECTS = {CanalplusVideo: fill_video}

    def iter_resources(self, objs, split_path):
        if BaseVideo in objs:
            return self.browser.iter_resources(split_path)
