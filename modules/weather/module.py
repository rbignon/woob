# Copyright(C) 2012 Arno Renevier
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


from woob.capabilities.weather import CapWeather
from woob.tools.backend import Module

from .browser import WeatherBrowser


__all__ = ["WeatherModule"]


class WeatherModule(Module, CapWeather):
    NAME = "weather"
    MAINTAINER = "Arno Renevier"
    EMAIL = "arno@renevier.net"
    VERSION = "3.7"
    DESCRIPTION = "Get forecasts from weather.com"
    LICENSE = "AGPLv3+"
    BROWSER = WeatherBrowser

    def iter_city_search(self, pattern):
        return self.browser.iter_city_search(pattern)

    def get_current(self, city_id):
        return self.browser.get_current(city_id)

    def iter_forecast(self, city_id):
        return self.browser.iter_forecast(city_id)
