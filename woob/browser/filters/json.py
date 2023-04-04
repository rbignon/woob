# Copyright(C) 2014-2021 Romain Bignon
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

from __future__ import annotations

from typing import Callable, Any

from .base import _Filter, _NO_DEFAULT, Filter, debug, ItemNotFound


__all__ = ['Dict']


class NotFound:
    def __repr__(self):
        return 'NOT_FOUND'

_NOT_FOUND = NotFound()


class Dict(Filter):
    """Filter to find elements in a dictionary or list.

    Note that a selector defined as None or an empty string will be equivalent
    to selecting the root of the provided document, as for None.

    :param selector: Input selector to use on the object.
    :param default: Default value is an element of the chain is not found, or
        if a type mismatch occurs.

    >>> d = {'a': {'b': 'c', 'd': None}}
    >>> Dict('')(d)
    {'a': {'b': 'c', 'd': None}}
    >>> Dict()(d)
    {'a': {'b': 'c', 'd': None}}
    >>> Dict('a/b')(d)
    'c'
    >>> Dict('a')(d)
    {'b': 'c', 'd': None}
    >>> Dict('notfound')(d)
    Traceback (most recent call last):
        ...
    woob.browser.filters.base.ItemNotFound: Element ['notfound'] not found
    >>> Dict('notfound', default=None)(d)
    >>>
    """
    def __init__(self,
                 selector: str | _Filter | Callable | Any | None = None,
                 default: Any = _NO_DEFAULT):
        super().__init__(default=default)
        if selector is None or selector == '':
            self.selector = []
        elif isinstance(selector, str):
            self.selector = selector.split('/')
        elif callable(selector):
            self.selector = [selector]
        else:
            self.selector = selector

    def __getitem__(self, name):
        self.selector.append(name)
        return self

    @debug()
    def filter(self, value):
        if value is _NOT_FOUND:
            return self.default_or_raise(ItemNotFound(f'Element {self.selector!r} not found' % self.selector))

        return value

    @classmethod
    def select(cls, selector, item, obj=None, key=None):
        if isinstance(item, (dict, list)):
            content = item
        else:
            content = item.el

        for el in selector:
            if isinstance(content, list):
                el = int(el)
            elif isinstance(el, _Filter):
                el._key = key
                el._obj = obj
                el = el(item)
            elif callable(el):
                el = el(item)

            try:
                content = content[el]
            except (KeyError, IndexError, TypeError):
                return _NOT_FOUND

        return content
