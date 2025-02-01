# -*- coding: utf-8 -*-

# Copyright(C) 2010-2012 Romain Bignon
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
from json import loads

from woob.browser.elements import ItemElement, method
from woob.browser.filters.standard import CleanText, Env, Regexp, Type
from woob.browser.pages import HTMLPage
from woob.capabilities.base import NotAvailable

from ..video import YoupornVideo


class VideoPage(HTMLPage):
    @method
    class get_video(ItemElement):
        klass = YoupornVideo

        obj_author = CleanText('//div[has-class("submitByLink")]')
        # obj_date = Date('//div[@id="stats-date"]')
        obj_duration = NotAvailable
        obj_ext = "mp4"
        obj_id = Env("id")
        obj_rating = CleanText('//div[@class="videoRatingPercentage"]') & Regexp(pattern=r"(\d+)%") & Type(type=int)
        obj_rating_max = 100
        obj_thumbnail = NotAvailable
        obj_title = CleanText("//h1")

        def obj_url(self):
            return loads(re.search('videoUrl":(".*?")', self.page.text).group(1))
