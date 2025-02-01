# Copyright(C) 2015      Bezleputh
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


from woob.capabilities.travel import CapTravel
from woob.tools.backend import Module

from .browser import BlablacarBrowser


__all__ = ["BlablacarModule"]


class BlablacarModule(Module, CapTravel):
    NAME = "blablacar"
    DESCRIPTION = "blablacar website"
    MAINTAINER = "Bezleputh"
    EMAIL = "carton_ben@yahoo.fr"
    LICENSE = "AGPLv3+"
    VERSION = "3.7"

    BROWSER = BlablacarBrowser

    def iter_roadmap(self, departure, arrival, filters):
        return self.browser.get_roadmap(departure, arrival, filters)

    def iter_station_departures(self, station_id, arrival_id, date):
        return self.browser.get_station_departures(station_id, arrival_id, date)
