# -*- coding: utf-8 -*-

# Copyright(C) 2019      Guntra
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

from __future__ import unicode_literals
from weboob.capabilities.housing import Query, ADVERT_TYPES, POSTS_TYPES
from weboob.tools.capabilities.housing.housing_test import HousingTest
from weboob.tools.test import BackendTest


class LesterrainsTest(BackendTest, HousingTest):

    MODULE = 'lesterrains'

    # Fields to be checked for values across all items in housings list
    FIELDS_ALL_HOUSINGS_LIST = [
        "id", "url", "type", "advert_type", "house_type"
    ]

    # Fields to be checked for at least one item in housings list
    FIELDS_ANY_HOUSINGS_LIST = [
        "photos"
    ]

    # Fields to be checked for values across all items when querying
    # individually
    FIELDS_ALL_SINGLE_HOUSING = [
        "id", "url", "type", "advert_type", "house_type", "title", "area",
        "cost", "currency", "date", "location", "text", "phone"
    ]

    # Fields to be checked for values at least once for all items when querying
    # individually
    FIELDS_ANY_SINGLE_HOUSING = [
        "photos"
    ]

    def test_lesterrains_sale(self):
        query = Query()
        query.area_min = 500
        query.type = POSTS_TYPES.SALE
        query.cities = []
        for city in self.backend.search_city('montastruc la conseillere'):
            city.backend = self.backend.name
            query.cities.append(city)
        self.check_against_query(query)
