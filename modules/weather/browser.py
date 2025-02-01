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


from woob.browser import URL, PagesBrowser

from .pages import CityPage, WeatherPage


__all__ = ["WeatherBrowser"]


class WeatherBrowser(PagesBrowser):
    BASEURL = "https://weather.com"

    city_page = URL("/api/v1/p/redux-dal", CityPage)
    weather_page = URL("/weather/today/l/(?P<city_id>.*)", WeatherPage)

    def iter_city_search(self, pattern):
        params = [
            {
                "name": "getSunV3LocationSearchUrlConfig",
                "params": {"query": pattern, "language": "en-US", "locationType": "locale"},
            }
        ]

        headers = {"Host": "weather.com"}
        return self.city_page.go(json=params, headers=headers).iter_cities(pattern=pattern)

    def get_current(self, city_id):
        return self.weather_page.go(city_id=city_id).get_current()

    def iter_forecast(self, city_id):
        return self.weather_page.go(city_id=city_id).iter_forecast()
