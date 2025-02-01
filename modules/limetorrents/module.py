# Copyright(C) 2018 Julien Veyssier
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

from urllib.parse import quote_plus

from woob.capabilities.torrent import CapTorrent, Torrent
from woob.tools.backend import Module

from .browser import LimetorrentsBrowser


__all__ = ["LimetorrentsModule"]


class LimetorrentsModule(Module, CapTorrent):
    NAME = "limetorrents"
    MAINTAINER = "Julien Veyssier"
    EMAIL = "eneiluj@posteo.net"
    VERSION = "3.7"
    DESCRIPTION = "Limetorrents BitTorrent tracker"
    LICENSE = "AGPLv3+"
    BROWSER = LimetorrentsBrowser

    def get_torrent(self, id):
        return self.browser.get_torrent(id)

    def get_torrent_file(self, id):
        torrent = self.browser.get_torrent(id)
        if not torrent:
            return None

        resp = self.browser.open(torrent.url)
        return resp.content

    def iter_torrents(self, pattern):
        return self.browser.iter_torrents(quote_plus(pattern.encode("utf-8")))

    def fill_torrent(self, torrent, fields):
        if "files" in fields:
            tor = self.get_torrent(torrent.id)
            torrent.magnet = tor.magnet
            torrent.files = tor.files
        return torrent

    OBJECTS = {Torrent: fill_torrent}
