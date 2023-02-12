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

from woob.capabilities.picross import CapPicross, PicrossSolvedStatus
from woob.tools.backend import Module

from .browser import PuzzleMadnessBrowser

__all__ = ['PuzzleMadnessModule']


class PuzzleMadnessModule(Module, CapPicross):
    NAME = 'puzzlemadness'
    DESCRIPTION = "Puzzle Madness"
    MAINTAINER = 'Thomas Touhey'
    EMAIL = 'thomas@touhey.fr'
    LICENSE = 'LGPLv3+'
    VERSION = '3.3'

    BROWSER = PuzzleMadnessBrowser

    def iter_picross_puzzles(self, solved_status=PicrossSolvedStatus.UNKNOWN):
        return self.browser.iter_picrosses(solved_status)

    def get_picross_puzzle(self, id_):
        return self.browser.get_picross(id_)

    def submit_picross_puzzle_solution(self, puzzle, solution):
        raise NotImplementedError()
