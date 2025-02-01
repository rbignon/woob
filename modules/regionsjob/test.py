# Copyright(C) 2014      Bezleputh
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


import itertools

from woob.tools.test import BackendTest
from woob.tools.value import Value


class RegionsjobTest(BackendTest):
    MODULE = "regionsjob"

    def setUp(self):
        if not self.is_backend_configured():
            self.backend.config["website"] = Value(value="www.parisjob.com")
            self.backend.config["experience"] = Value(value="")
            self.backend.config["secteur"] = Value(value="")
            self.backend.config["contract"] = Value(value="CDI")
            self.backend.config["metier"] = Value(value="")

    def test_regionjob_search(self):
        l = list(itertools.islice(self.backend.search_job("informaticien"), 0, 41))
        assert len(l)
        assert l[0].id
        assert l[0].url
        assert l[0].publication_date
        assert l[0].society_name
        assert l[0].title

        advert = self.backend.get_job_advert(l[0].id, None)
        self.assertTrue(advert.url, f'URL for announce "{advert.id}" not found: {advert.url}')
        assert advert.id
        assert advert.publication_date
        assert advert.society_name
        assert advert.title

    def test_regionjob_advanced_search(self):
        l = list(itertools.islice(self.backend.advanced_search_job(), 0, 41))
        assert len(l)
        assert l[0].id
        assert l[0].url
        assert l[0].publication_date
        assert l[0].society_name
        assert l[0].title

        advert = self.backend.get_job_advert(l[0].id, None)
        self.assertTrue(advert.url, f'URL for announce "{advert.id}" not found: {advert.url}')
        assert advert.id
        assert advert.publication_date
        assert advert.society_name
        assert advert.title
