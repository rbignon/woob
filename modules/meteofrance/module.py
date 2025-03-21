# Copyright(C) 2010-2011 Cedric Defortis
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


from woob.capabilities.base import find_object
from woob.capabilities.weather import CapWeather, CityNotFound
from woob.tools.backend import Module

from .browser import MeteofranceBrowser


__all__ = ["MeteofranceModule"]


class MeteofranceModule(Module, CapWeather):
    NAME = "meteofrance"
    MAINTAINER = "Cedric Defortis"
    EMAIL = "cedric@aiur.fr"
    VERSION = "3.7"
    DESCRIPTION = "Get forecasts from the MeteoFrance website"
    LICENSE = "AGPLv3+"
    BROWSER = MeteofranceBrowser

    def get_current(self, city_id):
        return self.browser.get_current(self.get_city(city_id))

    def iter_forecast(self, city_id):
        return self.browser.iter_forecast(self.get_city(city_id))

    def iter_city_search(self, pattern):
        return self.browser.iter_city_search(pattern)

    def get_city(self, _id):
        cities = list(self.iter_city_search(_id))

        if len(cities) == 0:
            raise CityNotFound()

        try:
            return find_object(cities, id=_id, error=CityNotFound)
        except CityNotFound:
            return cities[0]
