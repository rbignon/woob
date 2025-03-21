# Copyright(C) 2019      Vincent A
#
# This file is part of a woob module.
#
# This woob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This woob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this woob module. If not, see <http://www.gnu.org/licenses/>.

from woob.browser.elements import DictElement, ItemElement, method
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import CleanDecimal, DateTime, Env, Format, Lower, Map, Regexp
from woob.browser.pages import JsonPage
from woob.capabilities.address import GeoCoordinates, PostalAddress
from woob.capabilities.gauge import Gauge, GaugeMeasure, GaugeSensor


SENSOR_NAMES = {
    "PM25": "PM 2.5",
    "PM10": "PM 10",
    "O3": "O₃",
    "NO3": "NO₃",
    "NO2": "NO₂",
}


class AllPage(JsonPage):
    @method
    class iter_gauges(DictElement):
        def find_elements(self):
            return self.el.values()

        class item(ItemElement):
            klass = Gauge

            def condition(self):
                # sometimes the "date" field (which contains the hour) is empty
                # and no measure is present in it, so we discard it
                return bool(self.el["date"])

            def parse(self, el):
                for k in el:
                    self.env[k] = el[k]

                self.env["city"] = Regexp(Dict("commune"), r"^(\D+)")(self)

            obj_id = Dict("nom_court_sit")
            obj_name = Dict("isit_long")
            obj_city = Env("city")
            obj_object = "Pollution"

            obj__searching = Lower(
                Format(
                    "%s %s %s %s",
                    Dict("isit_long"),
                    Dict("commune"),
                    Dict("ninsee"),
                    Dict("adresse"),
                )
            )

            class obj_sensors(DictElement):
                def find_elements(self):
                    return [dict(zip(("key", "value"), tup)) for tup in self.el["indices"].items()]

                class item(ItemElement):
                    klass = GaugeSensor

                    obj_name = Map(Dict("key"), SENSOR_NAMES)
                    obj_gaugeid = Env("nom_court_sit")
                    obj_id = Format("%s.%s", obj_gaugeid, Dict("key"))
                    obj_unit = "µg/m³"

                    class obj_lastvalue(ItemElement):
                        klass = GaugeMeasure

                        obj_date = DateTime(
                            Format(
                                "%s %s",
                                Env("min_donnees"),
                                Env("date"),  # "date" contains the time...
                            )
                        )
                        obj_level = CleanDecimal(Dict("value"))

                    class obj_geo(ItemElement):
                        klass = GeoCoordinates

                        obj_latitude = CleanDecimal(Env("latitude"))
                        obj_longitude = CleanDecimal(Env("longitude"))

                    class obj_location(ItemElement):
                        klass = PostalAddress

                        obj_street = Env("adresse")
                        obj_postal_code = Env("ninsee")
                        obj_city = Env("city")
                        obj_region = "Ile-de-France"
                        obj_country = "France"
