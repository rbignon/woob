# Copyright(C) 2014      Alexandre Morignot
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


from datetime import datetime, timedelta

from woob.capabilities.calendar import Query
from woob.tools.test import BackendTest


class ResidentadvisorTest(BackendTest):
    MODULE = "residentadvisor"

    def test_searchcity(self):
        query = Query()
        query.city = "Melbourne"

        self.assertTrue(len(list(self.backend.search_events(query))) > 0)

        event = next(self.backend.search_events(query))
        self.assertTrue(self.backend.get_event(event.id))

    def test_datefrom(self):
        query = Query()
        later = datetime.now() + timedelta(days=31)
        query.start_date = later

        event = next(self.backend.search_events(query))
        self.assertTrue(later.date() <= event.start_date.date())

        event = self.backend.get_event(event.id)
        self.assertTrue(later.date() <= event.start_date.date())
