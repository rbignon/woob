# -*- coding: utf-8 -*-

# Copyright(C) 2010-2021 Julien Veyssier
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

from random import choice

from woob.capabilities.torrent import MagnetOnly
from woob.tools.compat import basestring
from woob.tools.test import BackendTest


class PiratebayTest(BackendTest):
    MODULE = 'piratebay'

    def test_torrent(self):
        # try something popular so we sometimes get a magnet-only torrent
        torrents = list(self.backend.iter_torrents('ubuntu linux'))
        if len(torrents):
            torrent = choice(torrents)
            full_torrent = self.backend.get_torrent(torrent.id)
            assert torrent.name
            assert full_torrent.name == torrent.name
            # I assume descriptions can be empty
            assert isinstance(full_torrent.description, basestring)
            try:
                assert self.backend.get_torrent_file(torrent.id)
            except MagnetOnly as e:
                assert e.magnet.startswith('magnet:')
                assert e.magnet == full_torrent.magnet
