# Copyright(C) 2023      Bezleputh
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
import itertools

from woob.capabilities.contact import SearchQuery
from woob.exceptions import ParseError
from woob.tools.test import BackendTest


class AumagasinTest(BackendTest):
    MODULE = 'aumagasin'

    def test_search_pagination(self):
        q = SearchQuery()
        q.name = 'V and B'
        res = list(itertools.islice(self.backend.search_contacts(q, None), 0, 80))
        self.assertNotEqual(len(res), 0)
        self.assertNotEmpty(res[0].name)
        self.assertNotEmpty(res[0].city)
        self.assertNotEmpty(res[0].postcode)
        self.assertNotEmpty(res[0].address)

    def test_search_number(self):
        q = SearchQuery()
        q.name = '4 murs'

        res = list(itertools.islice(self.backend.search_contacts(q, None), 0, 20))
        self.assertNotEqual(len(res), 0)
        self.assertNotEmpty(res[0].name)
        self.assertNotEmpty(res[0].city)
        self.assertNotEmpty(res[0].postcode)
        self.assertNotEmpty(res[0].address)

    def test_not(self):
        q = SearchQuery()
        q.name = 'brinbrin'

        try:
            self.backend.search_contacts(q, None)
            assert False
        except ParseError:
            assert True
        except Exception:
            assert False
