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

import re

from woob.browser.elements import method, DictElement, ItemElement
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import (
    Duration,
)
from woob.browser.pages import JsonPage
from woob.capabilities.base import NotAvailable
from woob.capabilities.image import Thumbnail
from woob.capabilities.video import BaseVideo


class ResultsPage(JsonPage):
    def build_doc(self, doc):
        doc = re.search(r"ytInitialData = (\{.*?\});</", doc)[1]
        return super().build_doc(doc)

    @method
    class iter_videos(DictElement):
        # youtube is VERY verbose
        item_xpath = "contents/twoColumnSearchResultsRenderer/primaryContents/sectionListRenderer/contents/0/itemSectionRenderer/contents"

        class item(ItemElement):
            klass = BaseVideo

            def condition(self):
                return "videoRenderer" in self.el

            def parse(self, el):
                self.el = el["videoRenderer"]

            obj_id = Dict("videoId")
            obj_title = Dict("title/runs/0/text")
            obj_description = Dict("detailedMetadataSnippets/0/snippetText/runs/0/text", default=NotAvailable)
            obj_duration = Duration(Dict("lengthText/simpleText", default='00:00:00'))  # Duration is set to "00:00:00" for live videos
            obj_author = Dict("ownerText/runs/0/text")
            # obj_url = BrowserURL("video", id=obj_id)  # let ytdl fill it

            class obj_thumbnail(ItemElement):
                klass = Thumbnail

                obj_url = Dict("thumbnail/thumbnails/0/url")
