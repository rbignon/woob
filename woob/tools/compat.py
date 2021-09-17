# -*- coding: utf-8 -*-

# Copyright(C) 2014 Romain Bignon
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

import sys
import pickle
import re

__all__ = ['unicode', 'long', 'basestring', 'range',
           'with_metaclass', 'unpickle',
           'quote', 'quote_plus', 'unquote', 'unquote_plus',
           'urlparse', 'urlunparse', 'urlsplit', 'urlunsplit',
           'urlencode', 'urljoin', 'parse_qs', 'parse_qsl',
           'getproxies', 'fullmatch',
           ]


try:
    unicode = unicode
except NameError:
    unicode = str

try:
    long = long
except NameError:
    long = int

try:
    basestring = basestring
except NameError:
    basestring = str


try:
    range = xrange
except NameError:
    range = range


try:
    from future.utils import with_metaclass
except ImportError:
    from six import with_metaclass


if sys.version_info.major == 2:
    class StrConv(object):
        def __str__(self):
            if hasattr(self, '__unicode__'):
                return self.__unicode__().encode('utf-8')
            else:
                return repr(self)
else:
    class StrConv(object):
        def __str__(self):
            if hasattr(self, '__unicode__'):
                return self.__unicode__()
            else:
                return repr(self)


try:
    from urllib import quote as _quote, quote_plus as _quote_plus, unquote as _unquote, unquote_plus as _unquote_plus, urlencode as _urlencode, getproxies
    from urlparse import urlparse, urlunparse, urljoin, urlsplit, urlunsplit, parse_qsl as _parse_qsl, parse_qs as _parse_qs

    def _reencode(s):
        if isinstance(s, unicode):
            s = s.encode('utf-8')
        return s

    def quote(p, *args, **kwargs):
        return _quote(_reencode(p), *args, **kwargs)

    def quote_plus(p, *args, **kwargs):
        return _quote_plus(_reencode(p), *args, **kwargs)

    def urlencode(d, *args, **kwargs):
        if hasattr(d, 'items'):
            d = list(d.items())
        else:
            d = list(d)

        d = [(_reencode(k), _reencode(v)) for k, v in d]

        return _urlencode(d, *args, **kwargs)

    def unquote(s):
        s = _reencode(s)
        return _unquote(s).decode('utf-8')

    def unquote_plus(s):
        s = _reencode(s)
        return _unquote_plus(s).decode('utf-8')

    def parse_qs(s, *args, **kwargs):
        s = _reencode(s)
        orig = _parse_qs(s, *args, **kwargs)
        return {k.decode('utf-8'): [vv.decode('utf-8') for vv in v] for k, v in orig.items()}

    def parse_qsl(s, *args, **kwargs):
        s = _reencode(s)
        return [(k.decode('utf-8'), v.decode('utf-8')) for k, v in _parse_qsl(s, *args, **kwargs)]

except ImportError:
    from urllib.parse import (
        urlparse, urlunparse, urlsplit, urlunsplit, urljoin, urlencode,
        quote, quote_plus, unquote, unquote_plus, parse_qsl, parse_qs,
    )
    from urllib.request import getproxies

def unpickle(pickled_data):
    if sys.version_info.major < 3:
        pyobject = pickle.loads(pickled_data)
    else:  # Assuming future Python versions will not remove encoding argument
        pyobject = pickle.loads(pickled_data, encoding='UTF-8')
    return pyobject


if sys.version >= '3.4':
    def fullmatch(pattern, string_to_parse, flags=0):
        return re.fullmatch(pattern, string_to_parse, flags)
else:
    def fullmatch(pattern, string_to_parse, flags=0):
        return re.match(r'%s$' % pattern, string_to_parse, flags)


if sys.version_info > (3, 4):
    def html_unescape(s):
        import html

        return html.unescape(s)
else:
    def html_unescape(s):
        from six.moves.html_parser import HTMLParser

        return HTMLParser().unescape(s)
