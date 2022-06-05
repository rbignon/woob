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

from .pages import PicrossListPage, PicrossPage


__all__ = ['PuzzleMadnessBrowser']


class PuzzleMadnessBrowser(PagesBrowser):
    BASEURL = 'https://puzzlemadness.co.uk/'

    picross_list = URL(r'picross$', PicrossListPage)
    picross = URL(r'picross/(?P<picross_id>\d+)', PicrossPage)

    # NOTE: Puzzle Madness has both nonograms and picrosses, but distinguishes
    #       them the following way:
    #
    #       "Picross puzzles are very similar to Nonogram puzzles. They are
    #        both picture logic puzzles where clues are given at the top and
    #        the left-hand side. The grid must be colored or left blank
    #        depending on the clues to reveal a pattern. In Nonogram puzzles,
    #        the picture is random, whereas Picross puzzles will reveal a
    #        hidden picture."
    #
    #       We might want to add nonogram support later; in the meanwhile,
    #       we add a 'p' at the beginning of the id for picrosses.

    def iter_picrosses(self, solved_status):
        if solved_status == PicrossSolvedStatus.SOLVED:
            return

        self.picross_list.go()
        for puzzle in self.page.iter_picrosses():
            # Keeping an explicit 'yield' in the function so that the
            # previous 'return' still returns an iterator.
            self.picross.go(picross_id=puzzle.id[1:])
            self.page.get_picross(obj=puzzle)
            yield puzzle

    def get_picross(self, id_):
        # Note that for some reason, appended letters to the argument won't
        # make the page fail, e.g. `/picross/584a` will be treated the same
        # way as `/picross/584`, but `/picross/5841` won't be, so we want to
        # limit to digits.

        m = re.fullmatch(r'p(\d+)', id_)
        if m is None:
            raise PicrossNotFound('Invalid format: should be p<number>')

        id_ = m.group(1)

        self.picross.go(picross_id=id_)
        if not self.picross.is_here():
            # Puzzle Madness redirects to picross list if a picross with
            # the given identifier does not exist.
            raise PicrossNotFound()

        return self.page.get_picross()
