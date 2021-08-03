# -*- coding: utf-8 -*-

# Copyright(C) 2012 Romain Bignon
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


from woob.browser import PagesBrowser, URL
from woob.capabilities.housing import TypeNotSupported, POSTS_TYPES
from woob.tools.compat import urlencode

from .pages import HousingPage, CitiesPage
from .constants import TYPES, RET


__all__ = ['PapBrowser']


class PapBrowser(PagesBrowser):

    BASEURL = 'https://www.pap.fr'
    housing = URL('/annonces/(?P<_id>.*)', HousingPage)
    search_page = URL('/recherche', HousingPage)
    search_result_page = URL('/annonce/.*', HousingPage)
    cities = URL(r'/json/ac-geo\?q=(?P<pattern>.*)', CitiesPage)

    def search_geo(self, pattern):
        return self.cities.open(pattern=pattern).iter_cities()

    def search_housings(self, type, cities, nb_rooms, area_min, area_max, cost_min, cost_max, house_types):

        if type not in TYPES:
            raise TypeNotSupported()

        self.session.headers.update({'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8'})

        data = {'geo_objets_ids': ','.join(cities),
                'surface[min]':   area_min or '',
                'surface[max]':   area_max or '',
                'prix[min]':      cost_min or '',
                'prix[max]':      cost_max or '',
                'produit':        TYPES.get(type, 'location'),
                'nb_resultats_par_page': 40,
                'action': 'submit',
                'nb_chambres[min]': '',
                'surface_terrain[min]': '',
                'surface_terrain[max]': '',
                'transport_objets_ids': '',
                'reference_courte': ''
                }

        if nb_rooms:
            data['nb_pieces[min]'] = nb_rooms
            data['nb_pieces[max]'] = nb_rooms

        if type == POSTS_TYPES.FURNISHED_RENT:
            data['tags[]'] = 'meuble'

        ret = []
        if type == POSTS_TYPES.VIAGER:
            ret = ['typesbien%5B%5D=viager']
        else:
            for house_type in house_types:
                if house_type in RET:
                    ret.append(f"typesbien%5B%5D={RET.get(house_type)}")

        _data = f"{urlencode(data)}&{'&'.join(ret)}"

        self.search_page.go(data=_data)
        assert self.search_result_page.is_here()
        return self.page.iter_housings(query_type=type)

    def get_housing(self, _id, housing=None):
        return self.housing.go(_id=_id).get_housing(obj=housing)
