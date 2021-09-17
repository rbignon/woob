# -*- coding: utf-8 -*-

# Copyright(C) 2010-2021  Nicolas Duhamel
#
# This file is part of woob.
#
# woob is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# woob is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with woob. If not, see <http://www.gnu.org/licenses/>.

from woob.capabilities.collection import Collection


def test_some():
    c = Collection([])
    assert c.basename is None
    assert c.parent_path is None
    assert c.path_level == 0

    c = Collection([u'lol'])
    assert c.basename == u'lol'
    assert c.parent_path == []
    assert c.path_level == 1

    c = Collection([u'lol', u'cat'])
    assert c.basename == u'cat'
    assert c.parent_path == [u'lol']
    assert c.path_level == 2

    c = Collection([u'w', u'e', u'e', u'b', u'o', u'o', u'b'])
    assert c.basename == u'b'
    assert c.parent_path == [u'w', u'e', u'e', u'b', u'o', u'o']
    assert c.path_level == 7
