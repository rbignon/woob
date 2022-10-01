# Copyright(C) 2022 Budget Insight
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

# flake8: compatible

import pytest

from woob.tools.url import (
    get_url_fragment_param, get_url_fragment_params, get_url_param,
    get_url_params, get_url_with_params,
)


@pytest.mark.parametrize('url,name,value', (
    ('https://example.org/?a=b&c=', 'a', 'b'),
    ('https://example.org/?a=b&c=', 'c', ''),
    ('https://example.org/?a=b&c&d=e', 'c', ''),
    ('https://example.org?a=b&a=c', 'a', 'c'),
    ('https://example.org?a=a#?a=b', 'a', 'a'),
))
def test_get_url_param(url, name, value):
    assert get_url_param(url, name) == value
    assert get_url_param(url, name, default=None) == value
    assert get_url_param(url, name, default='_MY_DEFAULT') == value


@pytest.mark.parametrize('url,name', (
    ('https://example.org/#?a=b&c=', 'a'),
    ('https://example.org/?a', 'b'),
    ('https://example.org/?#a', 'a'),
    ('https://example.org', 'a'),
    ('https://example.org/a', 'a'),
))
def test_get_url_param_fail(url, name):
    with pytest.raises(ValueError, match=r'has no query parameter'):
        get_url_param(url, name)

    assert get_url_param(url, name, default=None) is None
    assert get_url_param(url, name, default='_MY_DEFAULT') == '_MY_DEFAULT'


@pytest.mark.parametrize('url,name,value', (
    ('https://example.org/#a=b&c=', 'a', 'b'),
    ('https://example.org/#a=b&c=', 'c', ''),
    ('https://example.org/#a=b&c&d=e', 'c', ''),
    ('https://example.org?#a=b&a=c', 'a', 'c'),
    ('https://example.org?a=a#a=b', 'a', 'b'),
))
def test_get_url_fragment_param(url, name, value):
    assert get_url_fragment_param(url, name) == value
    assert get_url_fragment_param(url, name, default=None) == value
    assert get_url_fragment_param(url, name, default='_MY_DEFAULT') == value


@pytest.mark.parametrize('url,name', (
    ('https://example.org/?d#a=b&c=', 'd'),
    ('https://example.org/?a', 'b'),
    ('https://example.org/?#a', 'b'),
    ('https://example.org/#', ''),
    ('https://example.org', 'a'),
    ('https://example.org/a', 'a'),
))
def test_get_url_fragment_param_fail(url, name):
    with pytest.raises(ValueError, match=r'has no fragment parameter'):
        get_url_fragment_param(url, name)

    assert get_url_fragment_param(url, name, default=None) is None
    assert get_url_fragment_param(url, name, default='_MY_DEFAULT') == '_MY_DEFAULT'


@pytest.mark.parametrize('url,params', (
    ('https://example.org/?a=b&c=', {'a': 'b', 'c': ''}),
    ('https://example.org/#?a=b&c=', {}),
    ('https://example.org', {}),
    ('https://example.org?', {}),
    ('https://example.org?a', {'a': ''}),
    ('https://example.org?a=b&c', {'a': 'b', 'c': ''}),
    ('https://example.org?#a', {}),
    ('https://example.org?a&a=b', {'a': 'b'}),
))
def test_get_url_params(url, params):
    assert get_url_params(url) == params


@pytest.mark.parametrize('url,params', (
    ('https://example.org/#a=b&c=', {'a': 'b', 'c': ''}),
    ('https://example.org/?a=b&c=', {}),
    ('https://example.org', {}),
    ('https://example.org#', {}),
    ('https://example.org?#a', {'a': ''}),
    ('https://example.org#a=b&c', {'a': 'b', 'c': ''}),
    ('https://example.org#a&a=b', {'a': 'b'}),
))
def test_get_url_fragment_params(url, params):
    assert get_url_fragment_params(url) == params


@pytest.mark.parametrize('url,params,result', (
    ('https://a.com', {'a': 'b', 'c': ''}, 'https://a.com?a=b&c='),
    ('https://a.com?b=c&a', {'a': 'b'}, 'https://a.com?b=c&a=b'),
    ('https://a.com?a&b=c', {'a': 'b'}, 'https://a.com?a=b&b=c'),
    ('https://a.com?#a=b', {'a': 'c'}, 'https://a.com?a=c#a=b'),
    ('https://a.com', {}, 'https://a.com'),
    ('https://a.com/', {}, 'https://a.com/'),
    ('https://a.com?a=b&c&d=e', {'c': None}, 'https://a.com?a=b&d=e'),
    # NOTE: 'c' will be converted into 'c=' here.
    ('https://a.com?a=b&c&d=e', {'d': None, 'f': 'g'}, 'https://a.com?a=b&c=&f=g'),
    ('https://a.com?a=b&c', {'a': None, 'c': None}, 'https://a.com'),
))
def test_with_params(url, params, result):
    assert get_url_with_params(url, **params) == result
