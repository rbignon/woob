# -*- coding: utf-8 -*-

# Copyright(C) 2017      Antoine BOSSY
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
from woob.capabilities.housing import CapHousing, Housing, HousingPhoto, ADVERT_TYPES, POSTS_TYPES
from woob.tools.backend import Module
from .browser import FnaimBrowser

__all__ = ['FnaimModule']


class FnaimModule(Module, CapHousing):
    NAME = 'fnaim'
    DESCRIPTION = 'www.fnaim.fr website'
    MAINTAINER = 'Antoine BOSSY'
    EMAIL = 'mail+github@abossy.fr'
    LICENSE = 'AGPLv3+'
    VERSION = '3.2'

    BROWSER = FnaimBrowser

    def get_housing(self, id, housing=None):
        return self.browser.get_housing(id, housing)

    def search_city(self, pattern):
        return self.browser.search_city(pattern)

    def search_housings(self, query):
        if (
                len(query.advert_types) == 1 and
                query.advert_types[0] == ADVERT_TYPES.PERSONAL
        ):
            # Fnaim is pro only
            return list()

        # Sharing and furnished rent are not available in Fnaim searches
        if query.type == POSTS_TYPES.SHARING:
            return list()

        return self.browser.search_housings(query)

    def fill_housing(self, housing, fields):
        if len(fields) > 0:
            housing = self.browser.get_housing(housing.id, housing)
        return housing

    def fill_photo(self, photo, fields):
        if 'data' in fields and photo.url and not photo.data:
            photo.data = self.browser.open(photo.url).content
        return photo

    OBJECTS = {Housing: fill_housing, HousingPhoto: fill_photo}
