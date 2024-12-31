# -*- coding: utf-8 -*-

# Copyright(C) 2017      Vincent A
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

from woob.browser.elements import DictElement, ItemElement, method
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import DateTime, Field, Format
from woob.browser.pages import JsonPage
from woob.capabilities.file import LICENSES
from woob.capabilities.image import BaseImage, Thumbnail


class CollectionSearch(JsonPage):
    def do_stuff(self, _id):
        raise NotImplementedError()


class ImageSearch(JsonPage):
    def nb_pages(self):
        return self.doc['total_pages']

    @method
    class iter_images(DictElement):
        item_xpath = 'results'

        class item(ItemElement):
            klass = BaseImage

            obj_id = Dict('id')
            obj_nsfw = False
            obj_license = LICENSES.COPYRIGHT
            obj_author = Dict('user/name')
            obj_url = Dict('urls/full')
            obj_date = DateTime(Dict('created_at'))
            obj_title = Format('%s (%s)', Field('id'), Field('author'))
            obj_ext = 'jpg'

            def obj_thumbnail(self):
                return Thumbnail(Dict('urls/thumb')(self))
