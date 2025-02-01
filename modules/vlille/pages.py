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

from decimal import Decimal

from woob.browser.elements import ItemElement, TableElement, method
from woob.browser.filters.html import TableCell
from woob.browser.filters.standard import CleanText, DateTime, Field
from woob.browser.pages import HTMLPage
from woob.capabilities.base import NotLoaded
from woob.capabilities.gauge import Gauge, GaugeMeasure, GaugeSensor


class ListStationsPage(HTMLPage):
    @method
    class get_station_list(TableElement):
        item_xpath = "//div[@id='liste-station']/table/tbody/tr"
        head_xpath = "//div[@id='liste-station']/table/thead/tr/th/@class"

        col_id = "libelle"
        col_name = "Nom"
        col_city = "commune"
        col_adresse = "adresse"
        col_bikes = "nbVelosDispo"
        col_attachs = "nbPlacesDispo"
        col_status = "etat"

        class item(ItemElement):
            klass = Gauge

            obj_id = CleanText(TableCell("id"))
            obj_name = CleanText(TableCell("name"))
            obj_city = CleanText(TableCell("city"))
            obj_object = "vLille"

            @staticmethod
            def _create_bikes_sensor(value, gauge_id, last_update, adresse):
                levelbikes = GaugeSensor(gauge_id + "-bikes")
                levelbikes.name = "Bikes"
                levelbikes.address = "%s" % adresse
                lastvalue = GaugeMeasure()
                lastvalue.level = Decimal(value)
                lastvalue.date = last_update
                if lastvalue.level < 1:
                    lastvalue.alarm = "Empty station"
                levelbikes.lastvalue = lastvalue
                levelbikes.history = NotLoaded
                levelbikes.gaugeid = gauge_id
                return levelbikes

            @staticmethod
            def _create_attach_sensor(value, gauge_id, last_update, adresse):
                levelattach = GaugeSensor(gauge_id + "-attach")
                levelattach.name = "Attach"
                levelattach.address = "%s" % adresse
                lastvalue = GaugeMeasure()
                lastvalue.level = Decimal(value)
                lastvalue.date = last_update
                if lastvalue.level < 1:
                    lastvalue.alarm = "Full station"
                levelattach.lastvalue = lastvalue
                levelattach.history = NotLoaded
                levelattach.gaugeid = gauge_id
                return levelattach

            @staticmethod
            def _create_status_sensor(value, gauge_id, last_update, adresse):
                levelstatus = GaugeSensor(gauge_id + "-status")
                levelstatus.name = "Status"
                levelstatus.address = "%s" % adresse
                lastvalue = GaugeMeasure()
                lastvalue.level = Decimal(1) if value == "CONNECTEE" else Decimal(-1)
                if lastvalue.level < 1:
                    lastvalue.alarm = "Not available station"
                lastvalue.date = last_update
                levelstatus.lastvalue = lastvalue
                levelstatus.history = NotLoaded
                levelstatus.gaugeid = gauge_id
                return levelstatus

            def obj_sensors(self):
                sensors = []
                last_update = DateTime(CleanText('(//div[@class="maj"]/b)[1]', replace=[("à", "")]))(self)
                adresse = CleanText(TableCell("adresse"))(self)
                sensors.append(
                    self._create_bikes_sensor(
                        CleanText(TableCell("bikes"))(self), Field("id")(self), last_update, adresse
                    )
                )
                sensors.append(
                    self._create_attach_sensor(
                        CleanText(TableCell("attachs"))(self), Field("id")(self), last_update, adresse
                    )
                )
                sensors.append(
                    self._create_status_sensor(
                        CleanText(TableCell("status"))(self), Field("id")(self), last_update, adresse
                    )
                )
                return sensors
