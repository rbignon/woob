# -*- coding: utf-8 -*-

# Copyright(C) 2017      Vincent A
#
# This file is part of a weboob module.
#
# This weboob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This weboob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this weboob module. If not, see <http://www.gnu.org/licenses/>.

from weboob.browser.pages import JsonPage
from weboob.browser.elements import DictElement, ItemElement, method
from weboob.browser.filters.json import Dict
from weboob.browser.filters.standard import DateTime, Field, Format
from weboob.capabilities.image import BaseImage, Thumbnail
from weboob.capabilities.file import LICENSES


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
            obj_license = LICENSES.PD
            obj_author = Dict('user/name')
            obj_url = Dict('urls/full')
            obj_date = DateTime(Dict('created_at'))
            obj_title = Format('%s (%s)', Field('id'), Field('author'))
            obj_ext = 'jpg'

            def obj_thumbnail(self):
                return Thumbnail(Dict('urls/thumb')(self))
