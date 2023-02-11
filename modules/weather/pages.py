# -*- coding: utf-8 -*-

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
from woob.browser.elements import ItemElement, method, DictElement
from woob.browser.filters.base import _NO_DEFAULT, Filter
from woob.browser.filters.html import XPath
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import DateTime, Env, CleanText, Regexp, Format, Field
from woob.browser.pages import JsonPage, HTMLPage
from woob.capabilities.weather import Current, City, Temperature, Forecast
from woob.tools.json import json


class WeatherDict(Filter):
    def filter(self, value):
        pass

    def __init__(self, selector=None, default=_NO_DEFAULT):
        super(WeatherDict, self).__init__(selector, default)

    def __call__(self, item):
        self.selector = Format(self.selector, Env('query_key'),)(item)
        return Dict(selector=self.selector)(item)


class CityPage(JsonPage):
    @method
    class iter_cities(DictElement):
        item_xpath = None

        def parse(self, el):
            locations = el['dal']\
                          ['getSunV3LocationSearchUrlConfig']\
                          [f'language:en-US;locationType:locale;query:{self.env["pattern"]}']\
                          ['data']\
                          ['location']

            self.el = [{'name': address, 'id': place_id}
                       for place_id, address, city in zip(locations['placeId'], locations['address'], locations['city'])
                       if city is not None and self.env['pattern'].lower() in city.lower()]

        class item(ItemElement):
            klass = City

            obj_id = Dict('id')
            obj_name = Dict('name')


class WeatherPage(HTMLPage):
    def __init__(self, *args, **kwargs):
        HTMLPage.__init__(self, *args, **kwargs)
        json_doc = Regexp(CleanText(XPath('//script[contains(text(), "window.__data=JSON.parse")]/text()')),
                          r'window\.__data=JSON\.parse\("(.*)"\);')(self.doc)

        json_doc = json_doc.replace(r'\"', '"')
        json_doc = json_doc.replace(r'\\"', "'")

        self.doc = json.loads(json_doc)

    @method
    class get_current(ItemElement):
        klass = Current

        def parse(self, obj):
            self.env['query_key'] = next(iter(Dict('dal/getSunV3CurrentObservationsUrlConfig')(self).keys()))

        obj_id = Env('city_id')

        def obj_date(self):
            dt = DateTime(WeatherDict('dal/getSunV3CurrentObservationsUrlConfig/%s/data/validTimeLocal'))(self)
            return dt.date()

        def obj_temp(self):
            temp = WeatherDict('dal/getSunV3CurrentObservationsUrlConfig/%s/data/pressureAltimeter')(self)
            return Temperature(float(temp), 'F')

        def obj__feel_temp(self):
            temp = WeatherDict('dal/getSunV3CurrentObservationsUrlConfig/%s/data/temperatureFeelsLike')(self)
            temp = Temperature(float(temp), 'F')
            return f"{temp.ascelsius()}/{temp.asfahrenheit()}"

        obj_text = Format('%shPa (%s) - humidity %s%% - feels like %s - %s',
                          WeatherDict('dal/getSunV3CurrentObservationsUrlConfig/%s/data/pressureMeanSeaLevel'),
                          WeatherDict('dal/getSunV3CurrentObservationsUrlConfig/%s/data/pressureTendencyTrend'),
                          WeatherDict('dal/getSunV3CurrentObservationsUrlConfig/%s/data/relativeHumidity'),
                          Field('_feel_temp'),
                          WeatherDict('dal/getSunV3CurrentObservationsUrlConfig/%s/data/wxPhraseLong'))

    def iter_forecast(self):
        from datetime import datetime
        *_, forecast_key = iter(Dict('dal/getSunV3DailyForecastWithHeadersUrlConfig')(self.doc).keys())
        forecast = Dict(f'dal/getSunV3DailyForecastWithHeadersUrlConfig/{forecast_key}/data')(self.doc)
        for i in range(1, len(forecast['dayOfWeek'])):
            date = datetime.strptime(forecast['validTimeLocal'][i], '%Y-%m-%dT%H:%M:%S%z')
            tlow = float(forecast['temperatureMin'][i])
            thigh = float(forecast['temperatureMax'][i])
            text = forecast['narrative'][i]
            yield Forecast(date, tlow, thigh, text, 'F')
