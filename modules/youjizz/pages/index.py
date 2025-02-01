# -*- coding: utf-8 -*-

# Copyright(C) 2010-2014 Roger Philibert
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


from woob.browser.elements import ItemElement, ListElement, method
from woob.browser.filters.html import CSS, Link
from woob.browser.filters.standard import CleanText, Duration, Regexp
from woob.browser.pages import HTMLPage, pagination
from woob.capabilities.base import NotAvailable
from woob.capabilities.image import Thumbnail
from woob.capabilities.video import BaseVideo


class IndexPage(HTMLPage):
    @pagination
    @method
    class iter_videos(ListElement):
        item_xpath = '//span[@id="miniatura"]'

        next_page = Link('//a[text()="Next »"]')

        class item(ItemElement):
            klass = BaseVideo

            obj_id = CSS("a") & Link & Regexp(pattern=r"/videos/(.+)\.html")
            obj_title = CSS("span#title1") & CleanText
            obj_duration = CSS("span.thumbtime span") & CleanText & Duration | NotAvailable
            obj_nsfw = True

            def obj_thumbnail(self):
                thumbnail = Thumbnail(self.xpath(".//img")[0].attrib["data-original"])
                thumbnail.url = thumbnail.id.replace("http://", "https://")
                return thumbnail
