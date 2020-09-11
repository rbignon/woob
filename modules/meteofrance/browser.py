# -*- coding: utf-8 -*-

# Copyright(C) 2010-2011 Cedric Defortis
#
# This file is part of a weboob module.
#
# This weboob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This weboob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this weboob module. If not, see <http://www.gnu.org/licenses/>.

from weboob.browser import PagesBrowser, URL
from .pages import WeatherPage, SearchCitiesPage, HomePage

__all__ = ['MeteofranceBrowser']


class MeteofranceBrowser(PagesBrowser):
    BASEURL = 'https://meteofrance.com'

    cities = URL(r'/search/all\?term=(?P<pattern>.*)',
                 SearchCitiesPage)
    weather = URL(r'https://rpcache-aa.meteofrance.com/internet2018client/2.0/forecast\?lat=(?P<lat>.*)&lon=(?P<lng>.*)&id=&instants=&day=2',
                  WeatherPage)
    home = URL('', HomePage)

    def _fill_header(self):
        self.home.go()
        mfessions = self.session.cookies.get('mfsession')
        token = ''
        for c in mfessions:
            if c.isalpha():
                t = 97 if c.islower() else 65
                token += chr(t + (ord(c) - t + 13) % 26)
            else:
                token += c

        self.session.headers['Authorization'] = 'Bearer %s' % token
        self.session.headers['Sec-Fetch-Site'] = 'same-site'
        self.session.headers['Sec-Fetch-Mode'] = 'cors'

    def iter_city_search(self, pattern):
        return self.cities.go(pattern=pattern).iter_cities()

    def iter_forecast(self, city):
        if not self.session.headers.get('Authorization', None):
            self._fill_header()

        return self.weather.go(lng=city._lng, lat=city._lat).iter_forecast()

    def get_current(self, city):
        if not self.session.headers.get('Authorization', None):
            self._fill_header()

        return self.weather.go(lng=city._lng, lat=city._lat).get_current()
