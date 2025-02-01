# Copyright(C) 2016 Roger Philibert
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
from woob.browser.filters.html import CSS, Attr, Link
from woob.browser.filters.standard import CleanText, Duration, Env, Regexp
from woob.browser.pages import HTMLPage, pagination
from woob.capabilities.base import NotAvailable
from woob.capabilities.image import Thumbnail
from woob.capabilities.video import BaseVideo


class IndexPage(HTMLPage):
    @pagination
    @method
    class iter_videos(ListElement):
        item_xpath = '//li[has-class("videoblock")]'

        next_page = Link('//a[text()="Next"]')

        class item(ItemElement):
            klass = BaseVideo

            obj_id = CSS("a") & Link & Regexp(pattern=r"viewkey=(.+)")
            obj_title = Attr('.//span[has-class("title")]/a', "title") & CleanText
            obj_duration = CSS("var.duration") & CleanText & Duration | NotAvailable
            obj_nsfw = True

            def obj_thumbnail(self):
                thumbnail = Thumbnail(
                    Attr('.//img[has-class("js-videoThumb")]', "data-path")(self).replace("{index}", "1")
                )
                thumbnail.url = thumbnail.id
                return thumbnail


class VideoPage(HTMLPage):
    @method
    class get_video(ItemElement):
        klass = BaseVideo

        obj_id = Env("id")
        obj_title = CleanText("//title")
        obj_nsfw = True
        obj_ext = "mp4"
        obj_url = (
            CleanText("//script") & Regexp(pattern=r'(https:\\/\\/[^"]+\.mp4[^"]+)"') & CleanText(replace=[("\\", "")])
        )
