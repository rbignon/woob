# -*- coding: utf-8 -*-

# Copyright(C) 2017      Phyks (Lucas Verney)
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

from woob.capabilities.housing import CapHousing, Housing, ADVERT_TYPES, HousingPhoto
from woob.tools.backend import Module
from .browser import FonciaBrowser

__all__ = ['FonciaModule']


class FonciaModule(Module, CapHousing):
    NAME = 'foncia'
    DESCRIPTION = u'Foncia housing website.'
    MAINTAINER = u'Phyks (Lucas Verney)'
    EMAIL = 'phyks@phyks.me'
    LICENSE = 'AGPLv3+'
    VERSION = '3.4'

    BROWSER = FonciaBrowser

    def get_housing(self, house_id):
        return self.browser.get_housing(house_id)

    def search_city(self, pattern):
        return self.browser.get_cities(pattern)

    def search_housings(self, query):
        if (
                len(query.advert_types) == 1 and
                query.advert_types[0] == ADVERT_TYPES.PERSONAL
        ):
            # Foncia is pro only
            return list()

        cities = ['%s' % c.id for c in query.cities if c.backend == self.name]

        if len(cities) == 0:
            return []

        return self.browser.search_housings(query, cities)

    def fill_housing(self, housing, fields):
        if len(fields) > 0:
            housing = self.browser.get_housing(housing.id, housing)

        if 'phone' in fields:
            housing.phone = self.browser.get_phone(housing.id)
        return housing

    def fill_photo(self, photo, fields):
        if 'data' in fields and photo.url and not photo.data:
            photo.data = self.browser.open(photo.url).content
        return photo

    OBJECTS = {Housing: fill_housing, HousingPhoto: fill_photo}
