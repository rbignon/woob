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
import re

from woob.capabilities.base import find_object
from woob.capabilities.gauge import CapGauge, Gauge, GaugeSensor, SensorNotFound
from woob.tools.backend import Module

from .browser import VlilleBrowser


__all__ = ["VlilleModule"]


class VlilleModule(Module, CapGauge):
    NAME = "vlille"
    DESCRIPTION = "Lille bike renting availability information"
    MAINTAINER = "Bezleputh"
    EMAIL = "carton_ben@yahoo.fr"
    VERSION = "3.7"
    LICENSE = "AGPLv3+"

    BROWSER = VlilleBrowser

    def iter_gauges(self, pattern=None):
        if pattern is None:
            for gauge in self.browser.get_station_list():
                yield gauge
        else:
            lowpattern = pattern.lower()
            for gauge in self.browser.get_station_list():
                if lowpattern in gauge.name.lower():
                    yield gauge

    def iter_sensors(self, gauge, pattern=None):
        if not isinstance(gauge, Gauge):
            gauge = find_object(self.iter_gauges(), id=gauge, error=SensorNotFound)

        if pattern is None:
            for sensor in gauge.sensors:
                yield sensor
        else:
            lowpattern = pattern.lower()
            for sensor in gauge.sensors:
                if lowpattern in sensor.name.lower():
                    yield sensor

    def get_last_measure(self, sensor):
        if not isinstance(sensor, GaugeSensor):
            sensor = self._get_sensor_by_id(sensor)
        if sensor is None:
            raise SensorNotFound()
        return sensor.lastvalue

    def _get_sensor_by_id(self, _id):
        re_sensor_id = re.search(r"(\d+)-(bikes|attach|status)", _id, re.IGNORECASE)
        if re_sensor_id:
            gauge = re_sensor_id.group(1)
            pattern = re_sensor_id.group(2)
            sensor_generator = self.iter_sensors(gauge, pattern)
            if sensor_generator:
                return next(sensor_generator)
            else:
                return None
        return None
