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

import re
from urllib.parse import (
    urlparse, urlunparse, urlsplit, urlunsplit, urljoin, urlencode,
    quote, quote_plus, unquote, unquote_plus, parse_qsl, parse_qs,
)

from six.moves.html_parser import HTMLParser
try:
    from future.utils import with_metaclass
except ImportError:
    from six import with_metaclass


__all__ = ['unicode', 'long', 'basestring', 'range',
           'with_metaclass',
           'quote', 'quote_plus', 'unquote', 'unquote_plus',
           'urlparse', 'urlunparse', 'urlsplit', 'urlunsplit',
           'urlencode', 'urljoin', 'parse_qs', 'parse_qsl',
           'fullmatch',
           ]


unicode = str
long = int
basestring = str
range = range


class StrConv(object):
    def __str__(self):
        if hasattr(self, '__unicode__'):
            return self.__unicode__()
        else:
            return repr(self)




fullmatch = re.fullmatch


def html_unescape(s):
    return HTMLParser().unescape(s)
