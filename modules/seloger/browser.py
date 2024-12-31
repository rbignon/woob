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

from woob.browser import URL, PagesBrowser
from woob.browser.profiles import Firefox
from woob.capabilities.housing import POSTS_TYPES, TypeNotSupported

from .constants import BASE_URL, RET, TYPES
from .pages import CitiesPage, ErrorPage, HousingPage, SearchResultsPage


__all__ = ['SeLogerBrowser']


class SeLogerBrowser(PagesBrowser):
    BASEURL = BASE_URL
    PROFILE = Firefox()
    cities = URL(r'https://autocomplete.svc.groupe-seloger.com/auto/complete/0/Ville/6\?text=(?P<pattern>.*)',
                 CitiesPage)
    search = URL(r'/list.html\?(?P<query>.*)&LISTING-LISTpg=(?P<page_number>\d+)', SearchResultsPage)
    housing = URL(r'/(?P<_id>.+)/detail.htm',
                  r'/annonces/.+',
                  HousingPage)
    captcha = URL(r'http://validate.perfdrive.com', ErrorPage)

    def search_geo(self, pattern):
        return self.cities.open(pattern=pattern).iter_cities()

    def search_housings(self, _type, cities, nb_rooms, area_min, area_max,
                        cost_min, cost_max, house_types, advert_types):

        price = '{}/{}'.format(cost_min or '0', cost_max or 'Nan')
        surface = '{}/{}'.format(area_min or '0', area_max or 'Nan')

        rooms = ''
        if nb_rooms:
            rooms = '&rooms={}'.format(nb_rooms if nb_rooms <= 5 else 5)

        viager = ""
        if _type not in TYPES:
            raise TypeNotSupported()
        elif _type != POSTS_TYPES.VIAGER:
            _type = '{}'.format(TYPES.get(_type))
            viager = "&natures=1,2,4"
        else:
            _type = TYPES.get(_type)

        places = ','.join(['{}'.format(c) for c in cities])
        places = '[{{"inseeCodes": [{}]}}]'.format(places)

        ret = ','.join([RET.get(t) for t in house_types if t in RET])

        query = "projects={}{}&places={}&types={}&price={}&surface={}{}&enterprise=0&qsVersion=1.0"\
            .format(_type,
                    viager,
                    places,
                    ret,
                    price,
                    surface,
                    rooms)

        return self.search.go(query=query,
                              page_number=1).iter_housings(query_type=_type,
                                                           advert_types=advert_types,
                                                           ret=ret)

    def get_housing(self, _id, obj=None):
        return self.housing.go(_id=_id).get_housing(obj=obj)
