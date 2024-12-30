# -*- coding: utf-8 -*-

# Copyright(C) 2013      Bezleputh
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

from urllib.parse import urlencode

from woob.browser import URL, PagesBrowser

from .pages import AdvertPage, SearchPage


__all__ = ['PoleEmploiBrowser']


class PoleEmploiBrowser(PagesBrowser):
    BASEURL = 'https://candidat.pole-emploi.fr'

    advert = URL(r'/offres/recherche/detail/(?P<id>.*)', AdvertPage)
    search = URL(r'/offres/recherche\?(?P<param>.*?)',
                 r'/offres/recherche\?motsCles=(?P<pattern>.*?)', SearchPage)

    def search_job(self, pattern=None):
        return self.search.go(pattern=pattern).iter_job_adverts()

    def decode_place(self, splitted_place):
        return splitted_place[2] + splitted_place[1][0]

    def advanced_search_job(self, metier='', place=None, contrat=None, salary=None,
                            qualification=None, limit_date=None, domain=None):

        data = {}
        data['lieux'] = self.decode_place(place.split('|'))
        data['offresPartenaires'] = True
        data['rayon'] = 10
        data['tri'] = 0
        data['typeContrat'] = contrat
        data['qualification'] = qualification
        data['salaireMin'] = salary
        data['uniteSalaire'] = 'A'
        data['emission'] = limit_date
        data['domaine'] = domain
        data['motsCles'] = metier

        return self.search.go(param=urlencode(data)).iter_job_adverts()

    def get_job_advert(self, id, advert):
        return self.advert.go(id=id).get_job_advert(obj=advert)
