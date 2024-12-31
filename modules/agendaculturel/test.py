# -*- coding: utf-8 -*-

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


from datetime import datetime

from woob.tools.test import BackendTest
from woob.tools.value import Value


class AgendaculturelTest(BackendTest):
    MODULE = 'agendaculturel'

    def setUp(self):
        if not self.is_backend_configured():
            self.backend.config['place'] = Value(value='paris')

    def test_agendaculturel(self):
        _ = list(self.backend.list_events(datetime.now()))
        assert len(_)
        event = self.backend.get_event(_[0].id)
        self.assertTrue(event.url, 'URL for event "%s" not found: %s' % (event.id, event.url))
