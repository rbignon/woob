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

from urllib.parse import quote_plus

from woob.browser import PagesBrowser, URL
from woob.capabilities.housing import HOUSE_TYPES, POSTS_TYPES
from woob.tools.json import json
from .constants import QUERY_TYPES, QUERY_HOUSE_TYPES
from .pages import SearchCityPage, SearchPage, HousingPage


class FnaimBrowser(PagesBrowser):
    BASEURL = 'https://www.fnaim.fr'

    cities = URL(r'/include/ajax/ajax.localite.autocomplete.php\?term=(?P<term>)', SearchCityPage)
    search = URL('/include/ajax/annonce/ajax.annonceList.php',
                 r'/18-location.htm\?.*',
                 r'/17-acheter.htm\?.*',
                 SearchPage)
    housing = URL(r'/annonce-immobiliere/(?P<id>.+)/1[8|7]-.*.htm', HousingPage)

    def __init__(self, *args, **kwargs):
        super(FnaimBrowser, self).__init__(*args, **kwargs)

    def search_city(self, term):
        return self.cities.open(term=term).iter_cities()

    def get_housing(self, housing_id, housing):
        return self.housing.open(id=housing_id).get_housing(obj=housing)

    def search_housings(self, query):
        def none_to_empty(field):
            return '' if field is None else field

        if HOUSE_TYPES.UNKNOWN in query.house_types:
            types = [f'TYPE[]={t}' for t in QUERY_HOUSE_TYPES[HOUSE_TYPES.UNKNOWN]]
        else:
            types = []
            for house_type in query.house_types:
                types.extend([f'TYPE[]={t}' for t in QUERY_HOUSE_TYPES[house_type]])
        types_search = '&'.join(types)

        cities = []
        for city in query.cities:
            label = city.name.capitalize().replace(' ', '+')
            splitted_id = city.id.split('#')
            cities.append({
                'label': label,
                'id': splitted_id[0],
                'type': splitted_id[1],
                'insee': splitted_id[2],
            })

        meuble = 'MEUBLE[0]=1' if query.type == POSTS_TYPES.FURNISHED_RENT else ''
        localities = f'localites={quote_plus(json.dumps(cities))}'
        transaction = f'TRANSACTION={QUERY_TYPES[query.type]}'
        nb_pieces = f'NB_PIECES[0]={none_to_empty(query.nb_rooms)}&NB_PIECES[1]='
        surfaces = f'SURFACE[0]={none_to_empty(query.area_min)}&SURFACE[1]={none_to_empty(query.area_max)}'
        prix = f'PRIX[0]={none_to_empty(query.cost_min)}&PRIX[1]={none_to_empty(query.cost_max)}'
        nb_chambres = 'NB_CHAMBRES[0]=&NB_CHAMBRES[1]='
        terrain = 'SURFACE_TERRAIN[0]=&SURFACE_TERRAIN[1]='
        op = "op=CEN_VTE_PRIX_VENTE+asc%2CTRI_PRIX+asc%2CCEN_MDT_DTE_CREATION+desc&cp=d41d8cd98f00b204e980&mp=11&ip=1"

        data = '&'.join([transaction, localities, types_search,
                         nb_pieces, surfaces, prix, nb_chambres,
                         terrain, meuble, op])

        headers = {
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
        }

        return self.search.go(data=data, headers=headers).iter_housings()
