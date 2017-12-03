# -*- coding: utf-8 -*-

# Copyright(C) 2017      Antoine BOSSY
#
# This file is part of weboob.
#
# weboob is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# weboob is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with weboob. If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals

from weboob.browser import PagesBrowser, URL
from weboob.capabilities.housing import HOUSE_TYPES
from weboob.tools.json import json

from .pages import SearchCityPage, SearchPage, HousingPage
from .constants import QUERY_TYPES, QUERY_HOUSE_TYPES


class FnaimBrowser(PagesBrowser):
    BASEURL = 'https://www.fnaim.fr'

    cities = URL(r'/include/ajax/ajax.localite.autocomplete.php\?term=(?P<term>)', SearchCityPage)
    search = URL(r'/18-louer.htm\?localites=(?P<localities>.+)(?P<types>.+)&SURFACE_MIN=(?P<surface_min>\d*)&SURFACE_MAX=(?P<surface_max>\d*)&PRIX_MAX=(?P<prix_max>\d*)&PRIX_MIN=(?P<prix_min>\d*)&idtf=18&TRANSACTION=(?P<transaction>\d)&submit=Rechercher.*',
                 r'/18-louer.htm\?.*', r'/17-acheter.htm\?.*', SearchPage)
    housing = URL(r'/annonce-immobiliere/(?P<id>.+)/1[8|7]-.*.htm', HousingPage)

    def search_city(self, term):
        return self.cities.open(term=term).iter_cities()

    def get_housing(self, housing_id):
        return self.housing.open(id=housing_id).get_housing()

    def search_housings(self, query):
        types = []
        for house_type in query.house_types:
            if house_type == HOUSE_TYPES.UNKNOWN:
                types = ['&TYPE[]=%s' % t for t in QUERY_HOUSE_TYPES[house_type]]
                break
            types.extend(['&TYPE[]=%s' % t for t in QUERY_HOUSE_TYPES[house_type]])

        types_search = ''.join(types)

        transaction = QUERY_TYPES[query.type]

        def none_to_empty(field):
            if field is None:
                return ''
            return field

        cities = []
        for city in query.cities:
            label = city.name.capitalize().replace(' ', '+')
            cities.append({
                'label': label,
                'value': label,
                'id': city.id,
            })
        localities = json.dumps(cities)

        return self.search.go(localities=localities,
                              types=types_search,
                              transaction=transaction,
                              surface_min=none_to_empty(query.area_min),
                              surface_max=none_to_empty(query.area_max),
                              prix_max=none_to_empty(query.cost_max),
                              prix_min=none_to_empty(query.cost_min)).iter_housings()
