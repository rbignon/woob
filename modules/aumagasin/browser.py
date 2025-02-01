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

from woob.browser import URL, PagesBrowser
from woob.exceptions import ParseError

from .pages import EnseignesListPage, MagasinPage


class AumagasinBrowser(PagesBrowser):
    BASEURL = "https://www.au-magasin.fr"

    enseignes_list_page = URL(r"/enseignes/lettre/(?P<first_letter>\w*)/", EnseignesListPage)
    magasins_page = URL(r"/enseigne/(?P<enseigne_id>\d*-\w*)(?P<page>/\d+)?", MagasinPage)

    def search_contacts(self, query):
        assert query.name

        self.magasins_page.go(enseigne_id=self.get_enseigne_id(query.name), page=1)
        return self.page.iter_contacts()

    def get_enseigne_id(self, name: str):
        first_letter = name[0].upper()

        if not first_letter.isalpha():
            first_letter = "etc"

        self.enseignes_list_page.go(first_letter=first_letter)

        for item in self.page.list_enseignes():
            if item.id.upper() == name.upper():
                return item.url.split("/")[-1]

        raise ParseError(f"Aucune enseigne ne correspond à cette recherche: {name}")
