# -*- coding: utf-8 -*-

# Copyright(C) 2021 Romain Bignon
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

from woob.tools.compat import (
    range, unicode, basestring,
    quote, quote_plus, unquote, unquote_plus, urlencode, parse_qs, parse_qsl,
)

def test_base():
    assert type(range(3)) != list
    assert type(u'') == unicode
    assert type(b'') == bytes
    assert isinstance(u'', basestring)


def test_url():
    assert quote( 'foo=é&bar=qux ,/%') == u'foo%3D%C3%A9%26bar%3Dqux%20%2C/%25'
    assert quote(u'foo=é&bar=qux ,/%') == u'foo%3D%C3%A9%26bar%3Dqux%20%2C/%25'

    assert quote_plus( 'foo=é&bar=qux ,/%') == u'foo%3D%C3%A9%26bar%3Dqux+%2C%2F%25'
    assert quote_plus(u'foo=é&bar=qux ,/%') == u'foo%3D%C3%A9%26bar%3Dqux+%2C%2F%25'

    assert unquote( 'foo%3D%C3%A9%26bar%3Dqux%20%2C/%25') == u'foo=é&bar=qux ,/%'
    assert unquote(u'foo%3D%C3%A9%26bar%3Dqux%20%2C/%25') == u'foo=é&bar=qux ,/%'

    assert unquote_plus( 'foo%3D%C3%A9%26bar%3Dqux+%2C%2F%25') == u'foo=é&bar=qux ,/%'
    assert unquote_plus(u'foo%3D%C3%A9%26bar%3Dqux+%2C%2F%25') == u'foo=é&bar=qux ,/%'

    assert urlencode([( 'foo', u'é'), ( 'bar',  'qux ,/%')]) == u'foo=%C3%A9&bar=qux+%2C%2F%25'
    assert urlencode([(u'foo', u'é'), (u'bar', u'qux ,/%')]) == u'foo=%C3%A9&bar=qux+%2C%2F%25'

    assert urlencode(dict([( 'foo', u'é'), ( 'bar',  'qux ,/%')])) == u'foo=%C3%A9&bar=qux+%2C%2F%25'
    assert urlencode(dict([(u'foo', u'é'), (u'bar', u'qux ,/%')])) == u'foo=%C3%A9&bar=qux+%2C%2F%25'

    assert parse_qs( 'foo=%C3%A9&bar=qux+%2C%2F%25') == dict([(u'foo', [u'é']), (u'bar', [u'qux ,/%'])])
    assert parse_qs(u'foo=%C3%A9&bar=qux+%2C%2F%25') == dict([(u'foo', [u'é']), (u'bar', [u'qux ,/%'])])

    assert parse_qsl( 'foo=%C3%A9&bar=qux+%2C%2F%25') == [(u'foo', u'é'), (u'bar', u'qux ,/%')]
    assert parse_qsl(u'foo=%C3%A9&bar=qux+%2C%2F%25') == [(u'foo', u'é'), (u'bar', u'qux ,/%')]
