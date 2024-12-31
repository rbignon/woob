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


from woob.browser import URL, PagesBrowser
from woob.capabilities.housing import POSTS_TYPES
from woob.tools.json import json

from .constants import HOUSE_TYPES_LABELS, TRANSACTION_TYPE
from .pages import Cities, HousingPage, NeighborhoodPage, ResultsPage


class BieniciBrowser(PagesBrowser):
    BASEURL = 'https://www.bienici.com'

    cities = URL(r'https://res.bienici.com/suggest.json\?q=(?P<zipcode>.+)', Cities)
    results = URL(r'/realEstateAds.json\?filters=(?P<filters>.+)', ResultsPage)
    housing = URL(r'/realEstateAd.json\?id=(?P<housing_id>.*)', HousingPage)
    neighborhood = URL(r'/neighborhoodStatsById.json\?id=(?P<id_polygon>.*)', NeighborhoodPage)

    def get_cities(self, pattern):
        return self.cities.go(zipcode=pattern).get_city()

    def get_stations(self, id_polygon):
        return self.neighborhood.go(id_polygon=id_polygon).get_stations()

    def search_housing(self, query):

        # Sharing is not available in bienici searches
        if query.type == POSTS_TYPES.SHARING:
            return []

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
        if query.type == POSTS_TYPES.VIAGER:
            filters["isLifeAnnuitySaleOnly"] = True
        elif query.type == POSTS_TYPES.SALE:
            filters["isNotLifeAnnuitySale"] = True
        elif query.type == POSTS_TYPES.FURNISHED_RENT:
            filters["isFurnished"] = True

        for housing_type in dict_query['house_types']:
            filters['propertyType'] += HOUSE_TYPES_LABELS[housing_type]

        for city in dict_query['cities']:
            filters['zoneIdsByTypes']['zoneIds'].append(city.id)

        return self.results.go(filters=json.dumps(filters)).get_housings()

    def get_housing(self, housing_id, housing):
        return self.housing.go(housing_id=housing_id).get_housing(obj=housing)
