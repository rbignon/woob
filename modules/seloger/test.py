# -*- coding: utf-8 -*-

# Copyright(C) 2012  Romain Bignon
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

from woob.capabilities.housing import ADVERT_TYPES, POSTS_TYPES, Query
from woob.tools.capabilities.housing.housing_test import HousingTest
from woob.tools.test import BackendTest


class SeLogerTest(BackendTest, HousingTest):
    MODULE = 'seloger'

    FIELDS_ALL_HOUSINGS_LIST = [
        "id", "type", "advert_type", "house_type", "url", "title", "area",
        "utilities", "date", "location", "text"
    ]
    FIELDS_ANY_HOUSINGS_LIST = [
        "cost",  # Some posts don't have cost in seloger
        "currency",  # Same
        "photos",
    ]
    FIELDS_ALL_SINGLE_HOUSING = [
        "id", "url", "type", "advert_type", "house_type", "title", "area",
        "utilities", "date", "location", "text", "phone", "details"
    ]
    FIELDS_ANY_SINGLE_HOUSING = [
        "cost",  # Some posts don't have cost in seloger
        "currency",  # Same
        "photos",
        "rooms",
        "bedrooms",
        "DPE",
        "GES"
    ]
    DO_NOT_DISTINGUISH_FURNISHED_RENT = True

    def test_seloger_rent(self):
        query = Query()
        query.area_min = 20
        query.cost_max = 1500
        query.type = POSTS_TYPES.RENT
        query.cities = []
        for city in self.backend.search_city('paris'):
            city.backend = self.backend.name
            query.cities.append(city)
        self.check_against_query(query)

    def test_seloger_sale(self):
        query = Query()
        query.area_min = 10
        query.type = POSTS_TYPES.SALE
        query.cities = []
        for city in self.backend.search_city('lille'):
            city.backend = self.backend.name
            query.cities.append(city)
        self.check_against_query(query)

    def test_seloger_furnished_rent(self):
        query = Query()
        query.area_min = 20
        query.cost_max = 1500
        query.type = POSTS_TYPES.FURNISHED_RENT
        query.cities = []
        for city in self.backend.search_city('paris'):
            city.backend = self.backend.name
            query.cities.append(city)
        self.check_against_query(query)

    def test_seloger_viager(self):
        query = Query()
        query.type = POSTS_TYPES.VIAGER
        query.cities = []
        for city in self.backend.search_city('85'):
            city.backend = self.backend.name
            query.cities.append(city)
        self.check_against_query(query)

    def test_seloger_rent_personal(self):
        query = Query()
        query.area_min = 20
        query.cost_max = 1500
        query.type = POSTS_TYPES.RENT
        query.advert_types = [ADVERT_TYPES.PROFESSIONAL]
        query.cities = []
        for city in self.backend.search_city('paris'):
            city.backend = self.backend.name
            query.cities.append(city)
        self.check_against_query(query)
