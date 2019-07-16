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
from weboob.browser import PagesBrowser, URL
from weboob.browser.filters.standard import CleanText, Lower, Regexp
from weboob.capabilities.housing import (TypeNotSupported, POSTS_TYPES, HOUSE_TYPES)
from weboob.tools.compat import urlencode
from .pages import CitiesPage, SearchPage, HousingPage


class LesterrainsBrowser(PagesBrowser):

    BASEURL = 'http://www.les-terrains.com'

    TYPES = {
        POSTS_TYPES.SALE: 'vente'
    }
    
    RET = {
        HOUSE_TYPES.LAND: 'Terrain seul'
    }

    cities = URL('/api/get-search.php\?q=(?P<city>.*)', CitiesPage)

    search = URL('/index.php\?mode_aff=liste&ongletAccueil=Terrains&(?P<query>.*)&distance=0', SearchPage)

    housing = URL('/index.php\?page=terrains&mode_aff=un_terrain&idter=(?P<_id>\d+).*', HousingPage)
    
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
        return self.housing.go(_id = _id).get_housing(obj=housing)