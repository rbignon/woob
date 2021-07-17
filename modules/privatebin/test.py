# -*- coding: utf-8 -*-

# Copyright(C) 2021      Vincent A
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

# flake8: compatible

from woob.tools.test import BackendTest


class PrivatebinTest(BackendTest):
    MODULE = 'privatebin'

    def test_writeread(self):
        p = self.backend.new_paste(_id=None, contents='woob test')
        self.backend.browser.post_paste(p, 86400)

        assert p.url
        assert p.id
        assert p.title

        p2 = self.backend.get_paste(p.id)
        self.assertEqual(p2.contents, 'woob test')
        assert p.url.startswith(self.backend.browser.BASEURL)
        self.assertEqual(p.url, p2.url)
        self.assertEqual(p.id, p2.id)

        p3 = self.backend.get_paste(p.url)
        self.assertEqual(p.id, p3.id)
