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

from datetime import date, datetime

from woob.browser.elements import DictElement, ItemElement, method
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import CleanText, Field, Format
from woob.browser.pages import HTMLPage, JsonPage
from woob.capabilities.weather import City, Current, Direction, Forecast, Precipitation, Temperature


class SearchCitiesPage(JsonPage):
    @method
    class iter_cities(DictElement):
        # ignore_duplicate = True

        class item(ItemElement):
            klass = City

            def condition(self):
                return Dict("type")(self) == "VILLE_FRANCE"

            obj_id = Dict("cp")
            obj_name = Dict("name")
            obj__lng = Dict("lng")
            obj__lat = Dict("lat")


class HomePage(HTMLPage):
    pass


class WeatherPage(JsonPage):
    @method
    class get_current(ItemElement):
        klass = Current

        def parse(self, el):
            now = datetime.now()
            self.cpt = 0
            for item in Dict("properties/forecast")(el):
                if datetime.strptime(item["time"], "%Y-%m-%dT%H:%M:%S.%fZ") < now:
                    self.cpt = self.cpt + 1
                else:
                    break

        obj_date = date.today()

        def obj_id(self):
            return Dict(f"properties/forecast/{self.cpt}/time")(self)

        def obj_text(self):
            return Format(
                "%s - %s probability %s%% - Cloud coverage %s%% - Wind %s km/h %s° %s - Humidity %s%% - Pressure %s hPa",
                Dict(f"properties/forecast/{self.cpt}/weather_description"),
                Field("precipitation"),
                Field("precipitation_probability"),
                Field("wind_speed"),
                Dict(f"properties/forecast/{self.cpt}/total_cloud_cover"),
                Dict(f"properties/forecast/{self.cpt}/wind_direction"),
                Field("wind_direction"),
                Field("humidity"),
                Field("pressure"),
            )(self)

        def obj_precipitation_probability(self):
            return float(Dict(f"properties/forecast/{self.cpt}/rain_1h", default=0)(self))

        def obj_precipitation(self):
            return Precipitation.RA

        def obj_wind_direction(self):
            return Direction[CleanText(Dict(f"properties/forecast/{self.cpt}/wind_icon"), replace=[("O", "W")])(self)]

        def obj_wind_speed(self):
            return float(Dict(f"properties/forecast/{self.cpt}/wind_speed", default=0)(self))

        def obj_humidity(self):
            return float(Dict(f"properties/forecast/{self.cpt}/relative_humidity", default=0)(self))

        def obj_pressure(self):
            return float(Dict(f"properties/forecast/{self.cpt}/P_sea", default=0)(self))

        def obj_temp(self):
            return Temperature(float(Dict(f"properties/forecast/{self.cpt}/T", default=50)(self)), "C")

    @method
    class iter_forecast(DictElement):
        item_xpath = "properties/daily_forecast"

        class item(ItemElement):
            klass = Forecast

            obj_id = Dict("time")

            obj_date = Field("id")

            def obj_low(self):
                return Temperature(float(Dict("T_min", default=-50)(self)), "C")

            def obj_high(self):
                return Temperature(float(Dict("T_max", default=50)(self)), "C")

            def obj_text(self):
                return Format(
                    "%s - humidity %s%% / %s%% - UV index %s",
                    Dict("daily_weather_description"),
                    Dict("relative_humidity_min"),
                    Dict("relative_humidity_max"),
                    Dict("uv_index"),
                )(self)
