# -*- coding: utf-8 -*-

# Copyright(C) 2019      Guntra
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

from __future__ import unicode_literals

from urllib.parse import urlencode

from woob.browser import PagesBrowser, URL
from woob.capabilities.housing import POSTS_TYPES, HOUSE_TYPES

from .pages import CitiesPage, SearchPage, HousingPage


class LesterrainsBrowser(PagesBrowser):

    BASEURL = 'http://www.les-terrains.com'
    TYPES = {
        POSTS_TYPES.SALE: 'vente'
    }
    RET = {
        HOUSE_TYPES.LAND: 'Terrain seul'
    }
    cities = URL(r'/api/get-search.php\?q=(?P<city>.*)', CitiesPage)
    search = URL(r'/index.php\?mode_aff=liste&ongletAccueil=Terrains&(?P<query>.*)&distance=0', SearchPage)
    housing = URL(
        r'/index.php\?page=terrains&mode_aff=un_terrain&idter=(?P<_id>\d+).*',
        r'/index.php\?page=terrains&mode_aff=maisonterrain&idter=(?P<_id>\d+).*',
        HousingPage
    )

    def get_cities(self, pattern):
        return self.cities.open(city=pattern).get_cities()

    def search_housings(self, cities, area_min, area_max, cost_min, cost_max):

        def _get_departement(city):
            return city.split(';')[0][:2]

        def _get_ville(city):
            return city.split(';')[1]

        for city in cities:
            query = urlencode({
                "departement": _get_departement(city),
                "ville": _get_ville(city),
                "prixMin": cost_min or '',
                "prixMax": cost_max or '',
                "surfMin": area_min or '',
                "surfMax": area_max or '',
            })
            for house in self.search.go(query=query).iter_housings():
                yield house

    def get_housing(self, _id, housing=None):
        return self.housing.go(_id=_id).get_housing(obj=housing)
