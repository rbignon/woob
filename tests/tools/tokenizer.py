# -*- coding: utf-8 -*-

# Copyright(C) 2014 Oleg Plakhotniuk
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

from woob.tools.tokenizer import ReTokenizer


def test():
    t = ReTokenizer('foo bar baz', ' ', [('f', r'^f'), ('b', r'^b')])

    assert t.tok(0).is_f()
    assert t.tok(1).is_b()
    assert t.tok(2).is_b()

    assert t.tok(-1).is_eof()
    assert t.tok(3).is_eof()

    assert not t.tok(-1).is_f()
    assert not t.tok(0).is_b()
    assert not t.tok(0).is_eof()

    t = ReTokenizer('nogroup onegroup multigroup', ' ', [
        ('ng', r'^n.*$'),
        ('og', r'^one(g.*)$'),
        ('mg', r'^(m.*)(g.*)$')])

    assert t.tok(-1).value() is None
    assert t.tok(0).value() == 'nogroup'
    assert t.tok(1).value() == 'group'
    assert t.tok(2).value() == ('multi', 'group')
