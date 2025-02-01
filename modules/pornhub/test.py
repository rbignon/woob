# Copyright(C) 2016 Roger Philibert
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


from woob.capabilities.video import BaseVideo
from woob.tools.misc import limit
from woob.tools.test import BackendTest


class PornhubTest(BackendTest):
    MODULE = "pornhub"

    def test_search(self):
        self.assertTrue(len(self.backend.search_videos("anus", nsfw=False)) == 0)

        l = list(limit(self.backend.search_videos("anus", nsfw=True), 100))
        self.assertTrue(len(l) > 0)
        v = l[0]
        self.backend.fillobj(v, ("url",))
        self.assertTrue(v.url and v.url.startswith("http://"), f'URL for video "{v.id}" not found: {v.url}')
        r = self.backend.browser.open(v.url, stream=True)
        self.assertTrue(r.status_code == 200)

    def test_latest(self):
        l = list(limit(self.backend.iter_resources([BaseVideo], ["latest_nsfw"]), 100))
        self.assertTrue(len(l) > 0)
        v = l[0]
        self.backend.fillobj(v, ("url",))
        self.assertTrue(v.url and v.url.startswith("http://"), f'URL for video "{v.id}" not found: {v.url}')
