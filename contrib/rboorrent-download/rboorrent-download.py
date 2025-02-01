#!/usr/bin/env python3

# Copyright(C) 2017 Matthieu Weber
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.


import sys


class RboorrentDownload:
    def __init__(self, _id, no_tracker):
        self.id, self.backend_name = _id.split("@")
        self.no_tracker = no_tracker
        self.woob = Woob()
        self.backend = self.woob.load_backends(modules=[self.backend_name])[self.backend_name]

    def get_magnet(self, torrent):
        if self.no_tracker:
            return "&".join([_ for _ in torrent.magnet.split("&") if not _.startswith("tr=")])
        else:
            return torrent.magnet

    def write_meta(self, torrent):
        dest = f"meta-{torrent.id}-{torrent.name}.torrent"
        magnet = self.get_magnet(torrent)
        buf = "d10:magnet-uri%d:%se" % (len(magnet), magnet)
        try:
            with open(dest, "w") as f:
                f.write(buf)
        except OSError as e:
            print(f'Unable to write "{dest}": {e.message}')

    def write_torrent(self, torrent):
        dest = f"{torrent.id}-{torrent.name}.torrent"
        try:
            buf = self.backend.get_torrent_file(torrent.id)
            if buf:
                try:
                    with open(dest, "w") as f:
                        f.write(buf)
                except OSError as e:
                    print(f'Unable to write "{dest}": {e}')
        except Exception as e:
            print(f"Could not get torrent file for {self.id}@{self.backend_name}")

    def run(self):
        try:
            torrent = self.backend.get_torrent(self.id)
            if torrent.magnet:
                self.write_meta(torrent)
            else:
                self.write_torrent(torrent)
        except HTTPNotFound:
            print(f"Could not find {self.id}@{self.backend_name}")


def usage():
    prog_name = sys.argv[0].split("/")[-1]
    print("Usage: %s [-b] HASH@MODULE" % prog_name)
    print("  -b: don't include tracker URLs in the magnet link")
    sys.exit()


def parsed_args():
    if len(sys.argv) == 3 and sys.argv[1] == "-b":
        return (sys.argv[2], True)
    elif len(sys.argv) == 2:
        if sys.argv[1] in ["-h", "--help"]:
            usage()
        else:
            return (sys.argv[1], False)
    else:
        usage()


if __name__ == "__main__":
    args = parsed_args()

    from woob.browser.exceptions import HTTPNotFound
    from woob.core import Woob

    r = RboorrentDownload(*args)
    try:
        r.run()
    except Exception as e:
        print("Error: %s" % e.message)
