# Copyright(C) 2018      Vincent A
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

from woob.browser import URL, PagesBrowser
from woob.capabilities.contact import OpeningHours

from .pages import PlacePage, ResultsPage


class PagesjaunesBrowser(PagesBrowser):
    BASEURL = "https://www.pagesjaunes.fr"

    search = URL(
        r"/annuaire/chercherlespros\?quoiqui=(?P<pattern>[a-z0-9-]+)&ou=(?P<city>[a-z0-9-]+)&page=(?P<page>\d+)",
        ResultsPage,
    )
    company = URL(r"/pros/\d+", PlacePage)

    def simplify(self, name):
        return re.sub(r"[^a-z0-9-]+", "-", name.lower())

    def search_contacts(self, query):
        assert query.name
        assert query.city

        self.search.go(city=self.simplify(query.city), pattern=self.simplify(query.name), page=1)
        return self.page.iter_contacts()

    def fill_hours(self, contact):
        self.location(contact.url)
        contact.opening = OpeningHours()
        contact.opening.rules = list(self.page.iter_hours())
