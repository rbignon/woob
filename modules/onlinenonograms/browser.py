# flake8: compatible

# Copyright(C) 2022 Thomas Touhey <thomas@touhey.fr>
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

import re

from woob.browser.browsers import PagesBrowser
from woob.browser.url import URL
from woob.capabilities.picross import PicrossNotFound, PicrossSolvedStatus
from woob.exceptions import BrowserHTTPNotFound

from .pages import NonogramListPage, NonogramPage


__all__ = ["OnlineNonogramsBrowser"]


class OnlineNonogramsBrowser(PagesBrowser):
    BASEURL = "https://onlinenonograms.com/"

    nonogram_list = URL(r"index.php\?", NonogramListPage)
    nonogram = URL(r"(?P<nonogram_id>\d+)$", NonogramPage)

    def iter_picrosses(self, solved_status):
        if solved_status == PicrossSolvedStatus.SOLVED:
            return

        self.nonogram_list.go(
            params={
                "place": "catalog",
                "kat": "0",
                "color": "",
                "size": "",
                "star": "",
                "filtr": "all",
                "sort": "sortidd",  # descending identifier
                "noset": "2",
                "page": "1",
            }
        )

        for puzzle in self.page.iter_nonograms():
            self.nonogram.go(nonogram_id=puzzle.id)
            yield self.page.get_nonogram(obj=puzzle)

    def get_picross(self, id_):
        if not re.fullmatch(r"\d+", id_):
            raise PicrossNotFound()

        try:
            self.nonogram.go(nonogram_id=id_)
        except BrowserHTTPNotFound:
            raise PicrossNotFound()

        return self.page.get_nonogram()
