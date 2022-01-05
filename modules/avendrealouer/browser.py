# -*- coding: utf-8 -*-

# Copyright(C) 2017      ZeHiro
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

from __future__ import unicode_literals


from woob.browser import PagesBrowser, URL
from woob.capabilities.housing import HOUSE_TYPES, POSTS_TYPES

from .pages import CitiesPage, SearchPage, HousingPage
from .constants import QUERY_TYPES, QUERY_HOUSE_TYPES, FURNISHED_VALUES


class AvendrealouerBrowser(PagesBrowser):
    BASEURL = 'https://www.avendrealouer.fr'

    cities = URL(r'/common/api/localities\?term=(?P<term>)', CitiesPage)
    search = URL(r'/recherche.html\?pageIndex=1&sortPropertyName=Price&sortDirection=Ascending&searchTypeID=(?P<type_id>.*)&typeGroupCategoryID=(?P<group_id>.*)&transactionId=1&localityIds=(?P<location_ids>.*)&typeGroupIds=(?P<type_group_ids>.*)&roomComfortIds=(?P<rooms>.*)&minimumPrice=(?P<min_price>.*)&maximumPrice=(?P<max_price>.*)&minimumSurface=(?P<min_surface>.*)&maximumSurface=(?P<max_surface>.*)&furnished=(?P<furnished>.*)', SearchPage)
    housing = URL(r'/(?P<id>[vente|location].*).html', HousingPage)

    def __init__(self, datadome_cookie_search, datadome_cookie_detail, *args, **kwargs):
        super(AvendrealouerBrowser, self).__init__(*args, **kwargs)
        self.datadome_cookie_search = datadome_cookie_search
        self.datadome_cookie_detail = datadome_cookie_detail

    def get_cities(self, pattern):
        return self.cities.open(term=pattern).iter_cities()

    def search_housings(self, query):

        # There is no special search for shared appartments.
        if POSTS_TYPES.SHARING == query.type:
            return []

        type_id = QUERY_TYPES[query.type]['searchTypeID']
        group_id = QUERY_TYPES[query.type]['typeGroupCategoryID']
        furnished = FURNISHED_VALUES['YES'] if query.type == POSTS_TYPES.FURNISHED_RENT else FURNISHED_VALUES['BOTH']

        house_types = []
        for house_type in query.house_types:
            if house_type == HOUSE_TYPES.UNKNOWN:
                house_types = QUERY_HOUSE_TYPES[query.type][house_type]
                break
            house_types += QUERY_HOUSE_TYPES[query.type][house_type]

        type_group_ids = ','.join(house_types)
        location_ids = ','.join([city.id for city in query.cities])
        rooms = ','.join([str(_) for _ in
                          range(1 if not query.nb_rooms else query.nb_rooms if query.nb_rooms < 5 else 5, 6)])

        reg_exp = {
            'type_id': type_id,
            'group_id': group_id,
            'type_group_ids': type_group_ids,
            'rooms': rooms,
            'furnished': furnished,
            'min_price': query.cost_min if query.cost_min else '',
            'max_price': query.cost_max if query.cost_max else '',
            'min_surface': query.area_min if query.area_min else '',
            'max_surface': query.area_max if query.area_max else '',
            'location_ids': location_ids
        }

        if self.datadome_cookie_search:
            self.session.cookies.set(
                'datadome',
                self.datadome_cookie_search
            )
        return self.search.open(**reg_exp).iter_housings()

    def get_housing(self, housing_id, obj=None):
        self.session.cookies.set(
            'datadome',
            self.datadome_cookie_detail
        )
        return self.housing.go(id=housing_id.replace('#', '/')).get_housing(obj)
