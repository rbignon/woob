# -*- coding: utf-8 -*-

# Copyright(C) 2010-2021 Nicolas Duhamel
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

from woob.tools.path import WorkingPath


def test():
    wp = WorkingPath()
    assert wp.get() == []
    assert str(wp) == '/'
    wp.cd1(u'lol')
    assert wp.get() == [u'lol']
    assert str(wp) == '/lol'
    wp.cd1(u'cat')
    assert wp.get() == [u'lol', u'cat']
    assert str(wp) == '/lol/cat'
    wp.restore()
    assert str(wp) == '/lol'
    wp.home()
    assert wp.get() == []
    assert str(wp) == '/'
    wp.up()
    assert wp.get() == []
    assert str(wp) == '/'
    wp.location(['aa / aa', 'bbbb'])
    assert str(wp) == '/aa \/ aa/bbbb'
    wp.up()
    assert str(wp) == '/aa \/ aa'
    wp.cd1(u'héhé/hé')
    assert str(wp) == '/aa \/ aa/héhé\/hé'
