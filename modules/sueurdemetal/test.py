# Copyright(C) 2013      Vincent A
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

from woob.capabilities.calendar import CATEGORIES, Query
from woob.tools.test import BackendTest


class SueurDeMetalTest(BackendTest):
    MODULE = "sueurdemetal"

    def check_event(self, ev, full=False):
        self.assertTrue(ev.id)
        self.assertTrue(ev.summary)
        self.assertTrue(ev.description)
        self.assertTrue(ev.start_date)
        self.assertTrue(ev.end_date)
        self.assertTrue(ev.url)
        if full:
            self.assertTrue(ev.location)

    def test_sueurdemetal_searchcity(self):
        q = Query()
        q.city = "paris"
        self.assertTrue(len(list(self.backend.search_events(q))) > 0)

        ev = next(iter(self.backend.search_events(q)))
        self.check_event(ev)

        ev = self.backend.fillobj(ev)
        self.check_event(ev, full=True)

        ev = self.backend.get_event(ev.id)
        self.check_event(ev, full=True)

    def test_sueurdemetal_datefrom(self):
        q = Query()
        later = datetime.now() + timedelta(days=31)
        q.start_date = later

        ev = next(iter(self.backend.search_events(q)))
        self.check_event(ev)
        self.assertTrue(later.date() <= ev.start_date.date())

    def test_sueurdemetal_nocategory(self):
        q = Query()
        q.categories = [CATEGORIES.CINE]
        self.assertTrue(len(list(self.backend.search_events(q))) == 0)
