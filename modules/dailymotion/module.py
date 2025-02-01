# Copyright(C) 2011  Romain Bignon
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
from collections import OrderedDict

from woob.capabilities.collection import CapCollection, CollectionNotFound
from woob.capabilities.video import BaseVideo, CapVideo
from woob.tools.backend import BackendConfig, Module
from woob.tools.value import Value

from .browser import DailymotionBrowser


__all__ = ["DailymotionModule"]


class DailymotionModule(Module, CapVideo, CapCollection):
    NAME = "dailymotion"
    MAINTAINER = "Romain Bignon"
    EMAIL = "romain@weboob.org"
    VERSION = "3.7"
    DESCRIPTION = "Dailymotion video streaming website"
    LICENSE = "AGPLv3+"
    BROWSER = DailymotionBrowser

    resolution_choice = OrderedDict(
        [
            (k, f"{v} ({k})")
            for k, v in sorted({"480": "480p", "240": "240p", "380": "380p", "720": "720p", "1080": "1080p"}.items())
        ]
    )

    format_choice = ["m3u8", "mp4"]

    CONFIG = BackendConfig(
        Value("resolution", label="Resolution", choices=resolution_choice),
        Value("format", label="Format", choices=format_choice),
    )

    SORTBY = ["relevance", "rated", "visited", None]

    def create_default_browser(self):
        resolution = self.config["resolution"].get()
        format = self.config["format"].get()
        return self.create_browser(resolution=resolution, format=format)

    def get_video(self, _id):
        m = re.match(r"http://[w\.]*dailymotion\.com/video/(.*)", _id)
        if m:
            _id = m.group(1)

        if not _id.startswith("http"):
            return self.browser.get_video(_id)

    def search_videos(self, pattern, sortby=CapVideo.SEARCH_RELEVANCE, nsfw=False):
        return self.browser.search_videos(pattern, self.SORTBY[sortby])

    def fill_video(self, video, fields):
        if fields != ["thumbnail"]:
            # if we don't want only the thumbnail, we probably want also every fields
            video = self.browser.get_video(video.id, video)
        if "thumbnail" in fields and video.thumbnail:
            video.thumbnail.data = self.browser.open(video.thumbnail.url).content
        return video

    def iter_resources(self, objs, split_path):
        if BaseVideo in objs:
            collection = self.get_collection(objs, split_path)
            if collection.path_level == 0:
                yield self.get_collection(objs, ["latest"])
            if collection.split_path == ["latest"]:
                yield from self.browser.latest_videos()

    def validate_collection(self, objs, collection):
        if collection.path_level == 0:
            return
        if BaseVideo in objs and collection.split_path == ["latest"]:
            collection.title = "Latest Dailymotion videos"
            return
        raise CollectionNotFound(collection.split_path)

    OBJECTS = {BaseVideo: fill_video}
