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

from urllib.parse import urljoin

from woob.browser.elements import DictElement, ItemElement, method
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import BrowserURL, DateTime, Env, Field, Regexp
from woob.browser.pages import JsonPage
from woob.capabilities.base import BaseObject
from woob.capabilities.base import Field as FieldModel
from woob.capabilities.base import StringField
from woob.capabilities.date import DateField
from woob.capabilities.image import BaseImage


# TODO generalize this model for webcomics?
class ComicEntry(BaseObject):
    title = StringField("Title of the entry")
    description = StringField("Description")
    date = DateField("Date of the entry")
    cover = FieldModel("Cover image", BaseImage)
    images = FieldModel("Images in the entry", list)


class EntryElement(ItemElement):
    klass = ComicEntry

    obj_date = DateTime(Dict("datetime"))
    obj_title = Dict("title")
    obj_description = Dict("comments")
    obj_url = BrowserURL("user_page", page=Field("id"))

    class obj_cover(ItemElement):
        klass = BaseImage

        obj_url = BrowserURL("base_storage", rest=Dict("image"))


class EntriesPage(JsonPage):
    @method
    class iter_entries(DictElement):
        item_xpath = "comics/panels"

        class item(EntryElement):
            def condition(self):
                return "datetime" in self.el

            obj_id = Regexp(Dict("action"), r"^/(.+)/index.json$")


class EntryPage(JsonPage):
    @method
    class get_entry(EntryElement):
        def parse(self, el):
            # re-root element
            self.el = self.el["comics"]

        obj_cover = None
        obj_id = Env("id")

        class obj_images(DictElement):
            item_xpath = "panels"

            class item(ItemElement):
                klass = BaseImage

                def condition(self):
                    return "image" in self.el

                def obj_url(self):
                    return urljoin(self.page.url, self.el["image"])
