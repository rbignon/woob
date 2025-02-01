# Copyright(C) 2010-2014 Romain Bignon
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

import datetime

from woob.capabilities.travel import RoadmapFilters
from woob.tools.test import BackendTest


class TransilienTest(BackendTest):
    MODULE = "transilien"

    def test_stations(self):
        stations = list(self.backend.iter_station_search("aul"))
        self.assertTrue(len(stations) > 0)

    def test_departures(self):
        stations = list(self.backend.iter_station_search("paris"))
        self.assertTrue(len(stations) > 0)
        list(self.backend.iter_station_departures(stations[0].id))

    def test_roadmap(self):
        filters = RoadmapFilters()
        roadmap = list(self.backend.iter_roadmap("aul", "aub", filters))
        self.assertTrue(len(roadmap) > 0)

        filters.arrival_time = datetime.datetime.now() + datetime.timedelta(days=1)
        roadmap = list(self.backend.iter_roadmap("aul", "bag", filters))
        self.assertTrue(len(roadmap) > 0)

        filters.departure_time = datetime.datetime.now() + datetime.timedelta(days=1)
        roadmap = list(self.backend.iter_roadmap("gare du nord", "stade de boulogne", filters))
        self.assertTrue(len(roadmap) > 0)
