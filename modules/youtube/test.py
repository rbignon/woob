# Copyright(C) 2010-2021 Romain Bignon
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

import requests

from woob.tools.test import BackendTest


class YoutubeTest(BackendTest):
    MODULE = "youtube"

    def test_search(self):
        l = list(self.backend.search_videos("lol"))
        self.assertTrue(len(l) > 0)

        v = l[0]
        assert v.id
        assert v.title
        assert v.author
        self.assertTrue(any(el.description for el in l))
        self.assertTrue(any(el.duration for el in l))
        self.assertTrue(any(el.thumbnail.url.startswith("https://") for el in l))

        self.backend.fillobj(v, ("url",))
        self.assertTrue(v.url and v.url.startswith("https://"), f'URL for video "{v.id}" not found: {v.url}')
        requests.get(v.url, stream=True, timeout=30)

    def test_drm(self):
        v = self.backend.get_video("http://youtu.be/UxxajLWwzqY")
        self.backend.fillobj(v, ("url",))
        assert len(v.url)

        try:
            requests.get(v.url, stream=True, timeout=30)
        except requests.exceptions.RequestException:
            self.fail(f"can't open url {v.url}")

    def test_weirdchars(self):
        v = self.backend.get_video("https://www.youtube.com/watch?v=BaW_jenozKc")
        self.backend.fillobj(
            v,
            (
                "title",
                "url",
            ),
        )
        assert v.title
