# -*- coding: utf-8 -*-

# Copyright(C) 2017      Vincent A
#
# This file is part of a weboob module.
#
# This weboob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This weboob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this weboob module. If not, see <http://www.gnu.org/licenses/>.

from weboob.tools.test import BackendTest


class UnsplashTest(BackendTest):
    MODULE = 'unsplash'

    def test_search_img(self):
        it = self.backend.search_image('tree')
        images = [img for _, img in zip(range(20), it)]

        self.assertEqual(len(images), 20)
        for img in images:
            assert img.id
            assert img.title
            assert img.ext
            assert img.author
            assert img.date
            assert img.url

        self.backend.fillobj(img, 'data')
        assert img.data

        self.backend.fillobj(img, 'thumbnail')
        assert img.thumbnail.data
