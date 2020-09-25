# -*- coding: utf-8 -*-

# Copyright(C) 2020      Vincent A
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

from __future__ import unicode_literals

from weboob.capabilities.image import BaseImage
from weboob.tools.test import BackendTest


class InstagramTest(BackendTest):
    MODULE = 'instagram'

    def setUp(self):
        if not self.is_backend_configured():
            self.backend.config['user'] = Value(value='allanbarte')

    def test_iter(self):
        it = self.backend.iter_resources([BaseImage], [])
        # 15 will trigger pagination
        for _, img in zip(range(15), it):
            assert img.url
            assert img.id
            assert img.date

            assert img.title
            assert img.ext == 'jpg'

            print(img.url)
            #assert img.description

            assert img.author
            assert img.license

            img = self.backend.fillobj(img)
            assert img.data
