# -*- coding: utf-8 -*-

# Copyright(C) 2010-2011  Romain Bignon
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


import itertools
from random import choice

from woob.capabilities.video import BaseVideo
from woob.tools.test import BackendTest
from woob.tools.value import Value


class DailymotionTest(BackendTest):
    MODULE = "dailymotion"

    # Not easy to find a kids video which will always be there
    # This might break in the future
    KIDS_VIDEO_TITLE = "Telmo et Tula"

    def setUp(self):
        if not self.is_backend_configured():
            self.backend.config["resolution"] = Value(value="240")
            self.backend.config["format"] = Value(value="mp4")

    def test_search(self):
        l = list(itertools.islice(self.backend.search_videos("chirac"), 0, 20))
        self.assertTrue(len(l) > 0)
        v = choice(l)
        self.backend.fillobj(v, ("url",))
        self.assertTrue(v.url and v.url.startswith("http://"), 'URL for video "%s" not found: %s' % (v.id, v.url))

    def test_latest(self):
        l = list(itertools.islice(self.backend.iter_resources([BaseVideo], ["latest"]), 0, 20))
        assert len(l)
        v = choice(l)
        self.backend.fillobj(v, ("url",))
        self.assertTrue(v.url and v.url.startswith("http://"), 'URL for video "%s" not found: %s' % (v.id, v.url))

    def test_kids_video(self):
        l = list(itertools.islice(self.backend.search_videos(DailymotionTest.KIDS_VIDEO_TITLE), 0, 20))
        self.assertTrue(len(l) > 0)
        for elt in l[:10]:
            video_id = elt.id
            video = self.backend.get_video(video_id)
            self.assertIsNotNone(video.title)
            if DailymotionTest.KIDS_VIDEO_TITLE in video.title:
                self.assertTrue(
                    video.url and video.url.startswith("http://"),
                    'URL for video "%s" not found: %s' % (video.id, video.url),
                )
                return

        self.fail(
            "Can't find test video '%s' in kids.dailymotion.com video "
            "on dailymotion, maybe the test video should be changed." % DailymotionTest.KIDS_VIDEO_TITLE
        )
