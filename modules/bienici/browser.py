# -*- coding: utf-8 -*-

# Copyright(C) 2018      Antoine BOSSY
#
# This file is part of woob.
#
# woob is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# woob is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with woob. If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals


from woob.browser import PagesBrowser, URL
from woob.tools.json import json

from woob.capabilities.housing import POSTS_TYPES, HOUSE_TYPES
from .pages import Cities, ResultsPage, HousingPage


TRANSACTION_TYPE = {
    POSTS_TYPES.SALE: 'buy',
    POSTS_TYPES.RENT: 'rent',
    POSTS_TYPES.SALE: 'buy',
    POSTS_TYPES.FURNISHED_RENT: 'rent',
    POSTS_TYPES.SHARING: 'rent'
}


HOUSE_TYPES = {
    HOUSE_TYPES.APART: ['flat'],
    HOUSE_TYPES.HOUSE: ['house'],
    HOUSE_TYPES.PARKING: ['parking'],
    HOUSE_TYPES.LAND: ['terrain'],
    HOUSE_TYPES.OTHER: ['others', 'loft', 'shop', 'building', 'castle', 'premises', 'office', 'townhouse'],
    HOUSE_TYPES.UNKNOWN: []
}


class BieniciBrowser(PagesBrowser):
    BASEURL = 'https://www.bienici.com'

    cities = URL(r'https://res.bienici.com/suggest.json\?q=(?P<zipcode>.+)', Cities)
    results = URL(r'/realEstateAds.json\?filters=(?P<filters>.+)', ResultsPage)
    housing = URL(r'/realEstateAds-one.json\?filters=(?P<filters>.*)&onlyRealEstateAd=(?P<housing_id>.*)', HousingPage)

    def get_cities(self, pattern):
        return self.cities.go(zipcode=pattern).get_city()

    def search_housing(self, query):
        filters = {
            'size': 100,
            'page': 1,
            'resultsPerPage': 24,
            'maxAuthorizedResults': 2400,
            'sortBy': "relevance",
            'sortOrder': "desc",
            'onTheMarket': [True],
            'showAllModels': False,
            "zoneIdsByTypes": {
                'zoneIds': []
            },
            'propertyType': []
        }

        dict_query = query.to_dict()
        if dict_query['area_min']:
            filters['minArea'] = dict_query['area_min']

        if dict_query['area_max']:
            filters['maxArea'] = dict_query['area_max']

        if dict_query['cost_min']:
            filters['minPrice'] = dict_query['cost_min']

        if dict_query['cost_max']:
            filters['maxPrice'] = dict_query['cost_max']

        filters['filterType'] = TRANSACTION_TYPE[dict_query['type']]

        for housing_type in dict_query['house_types']:
            filters['propertyType'] += HOUSE_TYPES[housing_type]

        for city in dict_query['cities']:
            filters['zoneIdsByTypes']['zoneIds'].append(city.id)

        return self.results.go(filters=json.dumps(filters)).get_housings()

    def get_housing(self, housing_id):
        # This is to serialize correctly the JSON, and match the URL easier.
        filters = {
            'onTheMarket': [True]
        }
        return self.housing.go(housing_id=housing_id, filters=json.dumps(filters)).get_housing()
