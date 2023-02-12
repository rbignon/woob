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

from woob.capabilities.picross import (
    CapPicross, PicrossSolutionKind, PicrossSolvedStatus,
)
from woob.tools.backend import BackendConfig, Module
from woob.tools.value import ValueBackendPassword

from .browser import PixNCrossBrowser

__all__ = ['PixNCrossModule']


class PixNCrossModule(Module, CapPicross):
    NAME = 'pixncross'
    DESCRIPTION = "Pix'N'Cross"
    MAINTAINER = 'Thomas Touhey'
    EMAIL = 'thomas@touhey.fr'
    LICENSE = 'LGPLv3+'
    VERSION = '3.3'

    CONFIG = BackendConfig(
        ValueBackendPassword(
            'login',
            label="Nom d'utilisateur",
            required=False,
        ),
        ValueBackendPassword(
            'password',
            label='Mot de passe',
            required=False,
        ),
    )

    BROWSER = PixNCrossBrowser

    can_submit_picross_puzzle_solution = True

    def create_default_browser(self):
        return self.create_browser(
            self.config['login'].get(),
            self.config['password'].get(),
        )

    def iter_picross_puzzles(self, solved_status=PicrossSolvedStatus.UNKNOWN):
        return self.browser.iter_puzzles(solved_status)

    def get_picross_puzzle(self, id_):
        return self.browser.get_puzzle(id_)

    def submit_picross_puzzle_solution(self, puzzle, solution):
        if solution.kind != PicrossSolutionKind.PLACEMENTS:
            raise ValueError('Solution kind must be PLACEMENTS.')

        return self.browser.submit_solution(puzzle.id, solution)
