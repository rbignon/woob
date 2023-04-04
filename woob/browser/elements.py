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

from __future__ import annotations

from typing import Callable, Any, Type
import importlib
import os
import re
import sys
from collections import OrderedDict
from copy import deepcopy
import traceback
import warnings

import lxml.html

from woob.tools.log import getLogger, DEBUG_FILTERS
from woob.browser.pages import NextPage
from woob.capabilities.base import FetchError

from .filters.standard import _Filter, CleanText
from .filters.html import AttributeNotFound, XPathNotFound
from .filters.json import Dict


__all__ = [
    'AbstractElement',
    'DataError',
    'DictElement',
    'ItemElement',
    'ItemElementFromAbstractPage',
    'ListElement',
    'MetaAbstractItemElement',
    'SkipItem',
    'TableElement',
    'generate_table_element',
    'magic_highlight',
    'method',
]


def generate_table_element(doc, head_xpath, cleaner=CleanText):
    """
    Prints generated base code for TableElement/TableCell usage.
    It is intended for development purposes, typically in woob-debug.
    :param doc: lxml tree of the page (e.g. browser.page.doc)
    :param head_xpath: xpath of header columns (e.g. //table//th)
    :type head_xpath: str
    :param cleaner: cleaner class (Filter)
    :type cleaner: Filter
    """
    from unidecode import unidecode
    indent = 4
    headers = doc.xpath(head_xpath)
    cols = dict()
    for el in headers:
        th = cleaner.clean(el)
        cols.update({re.sub('[^a-zA-Z]', '_', unidecode(th)).lower(): th})

    print(' ' * indent + '@method')
    print(' ' * indent + 'class get_items(TableElement):')
    if cleaner is not CleanText:
        print(' ' * indent * 2 + 'cleaner = %s' % cleaner.__name__)
    print(' ' * indent * 2 + 'head_xpath = ' + repr(head_xpath))
    print(' ' * indent * 2 + 'item_xpath = ' + repr('...') + '\n')

    for col, name in cols.items():
        print(' ' * indent * 2 + 'col_' + col + ' = ' + repr(name))

    print('\n' + ' ' * indent * 2 + 'class item(ItemElement):')
    print(' ' * indent * 3 + 'klass = BaseObject' + '\n')

    for col in cols:
        print(' ' * indent * 3 + 'obj_' + col + ' = ' + "TableCell('%s') & CleanText()" % col)


class DataError(Exception):
    """
    Returned data from pages are incoherent.
    """


def method(klass):
    """
    Class-decorator to call it as a method.
    """

    def inner(self, *args, **kwargs):
        return klass(self)(*args, **kwargs)

    inner.klass = klass
    return inner


class AbstractElement:
    _creation_counter = 0

    condition: None | bool | _Filter | Callable[[], Any] = None
    """The condition to parse the element.

    This allows ignoring certain elements if certain fields are not valid,
    or if the element should actually be parsed using another class.

    This property can be defined as:

    * None or True, to signify that the element should be parsed regardless.
    * False, to signify that the element should not be parsed regardless.
    * A filter returning a falsy or non-falsy object, evaluated with the
      constructed document section (HTML element or JSON data) for the element.
    * A method returning a falsy or non-falsy object, evaluated with the
      element object directly.
    """

    def __new__(cls, *args, **kwargs):
        """ Accept any arguments, necessary for ItemElementFromAbstractPage __new__
        override.

        ItemElementFromAbstractPage, in its overridden __new__, removes itself from
        class hierarchy so its __new__ is called only once. In python 3, default
        (object) __new__ is then used for next instantiations but it's a slot/fixed
        version supporting only one argument (type to instanciate).
        """
        return object.__new__(cls)

    def __init__(self, page, parent=None, el=None):
        self.page = page
        self.parent = parent
        if el is not None:
            self.el = el
        elif parent is not None:
            self.el = parent.el
        else:
            self.el = page.doc

        parent_logger = None
        if self.page:
            parent_logger = self.page.logger
        self.logger = getLogger(self.__class__.__name__.lower(), parent_logger)

        self.fill_env(page, parent)

        # Used by debug
        self._random_id = AbstractElement._creation_counter
        AbstractElement._creation_counter += 1

        self.loaders = {}

    def use_selector(
        self,
        func: _Filter | 'ItemElement' | 'ListElement' | Callable[[], Any],
        key: str | None = None
    ):
        if isinstance(func, _Filter):
            func._obj = self
            func._key = key
            value = func(self)
        elif isinstance(func, type) and issubclass(func, ItemElement):
            value = func(self.page, self, self.el)()
        elif isinstance(func, type) and issubclass(func, ListElement):
            value = list(func(self.page, self, self.el)())
        elif callable(func):
            value = func()
        else:
            value = deepcopy(func)

        return value

    def parse(self, obj):
        pass

    def cssselect(self, *args, **kwargs):
        return self.el.cssselect(*args, **kwargs)

    def xpath(self, *args, **kwargs):
        return self.el.xpath(*args, **kwargs)

    def handle_loaders(self):
        for attrname in dir(self):
            m = re.match('load_(.*)', attrname)
            if not m:
                continue
            name = m.group(1)
            if name in self.loaders:
                continue
            loader = getattr(self, attrname)
            self.loaders[name] = self.use_selector(loader, key=attrname)

    def fill_env(self, page, parent=None):
        if parent is not None:
            self.env = deepcopy(parent.env)
        else:
            self.env = deepcopy(page.params)

    def check_condition(self):
        """Get whether our condition is respected or not."""
        if self.condition is None or self.condition is True:
            return True
        elif self.condition is False:
            return False
        elif isinstance(self.condition, _Filter):
            if self.condition(self.el):
                return True
        elif callable(self.condition):
            if self.condition():
                return True
        else:
            assert isinstance(self.condition, str)
            if self.el.xpath(self.condition):
                return True

        return False


class ListElement(AbstractElement):
    item_xpath = None
    empty_xpath = None
    flush_at_end = False
    ignore_duplicate = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.objects = OrderedDict()

    def __call__(self, *args, **kwargs):
        for key, value in kwargs.items():
            self.env[key] = value

        return self.__iter__()

    def find_elements(self):
        """
        Get the nodes that will have to be processed.
        This method can be overridden if xpath filters are not
        sufficient.
        """
        if self.item_xpath is not None:
            element_list = self.el.xpath(self.item_xpath)
            if element_list:
                for el in element_list:
                    yield el
            elif self.empty_xpath is not None and not self.el.xpath(self.empty_xpath):
                # Send a warning if no item_xpath node was found and an empty_xpath is defined
                self.logger.warning('No element matched the item_xpath and the defined empty_xpath was not found!')
        else:
            yield self.el

    def __iter__(self):
        if not self.check_condition():
            return

        self.parse(self.el)

        items = []
        for el in self.find_elements():
            for attrname in dir(self):
                attr = getattr(self, attrname)
                if isinstance(attr, type) and issubclass(attr, AbstractElement) and attr != type(self):
                    item = attr(self.page, self, el)
                    if not item.check_condition():
                        continue

                    item.handle_loaders()
                    items.append(item)

        for item in items:
            for obj in item:
                obj = self.store(obj)
                if obj and not self.flush_at_end:
                    yield obj

        if self.flush_at_end:
            for obj in self.flush():
                yield obj

        self.check_next_page()

    def flush(self):
        for obj in self.objects.values():
            yield obj

    def check_next_page(self):
        if not hasattr(self, 'next_page'):
            return

        next_page = getattr(self, 'next_page')
        try:
            value = self.use_selector(next_page)
        except (AttributeNotFound, XPathNotFound):
            return

        if value is None:
            return

        raise NextPage(value)


    def store(self, obj):
        if obj.id:
            if obj.id in self.objects:
                if self.ignore_duplicate:
                    self.logger.warning('There are two objects with the same ID! %s' % obj.id)
                    return
                else:
                    raise DataError('There are two objects with the same ID! %s' % obj.id)
            self.objects[obj.id] = obj
        return obj


class SkipItem(Exception):
    """
    Raise this exception in an :class:`ItemElement` subclass to skip an item.
    """


class _ItemElementMeta(type):
    """
    Private meta-class used to keep order of obj_* attributes in :class:`ItemElement`.
    """
    def __new__(mcs, name, bases, attrs):
        _attrs = []
        for base in bases:
            if hasattr(base, '_attrs'):
                _attrs += base._attrs

        filters = [(re.sub('^obj_', '', attr_name), attrs[attr_name]) for attr_name, obj in attrs.items() if attr_name.startswith('obj_')]
        # constants first, then filters, then methods
        filters.sort(key=lambda x: x[1]._creation_counter if hasattr(x[1], '_creation_counter') else (sys.maxsize if callable(x[1]) else 0))

        attrs['_class_file'], attrs['_class_line'] = traceback.extract_stack()[-2][:2]
        new_class = super().__new__(mcs, name, bases, attrs)
        new_class._attrs = _attrs + [f[0] for f in filters]
        return new_class


class ItemElement(AbstractElement, metaclass=_ItemElementMeta):
    _attrs = None
    klass: Type | None = None
    validate: Callable[[Any], bool] | None = None
    skip_optional_fields_errors: bool = False

    item_xpath: str | None = None
    """The xpath to reroot the element in.

    This will be evaluated only once the object and environment are set,
    so it can be defined as a property using ``self.obj`` and ``self.env``,
    i.e. call parameters.
    """

    class Index:
        pass

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.obj: Any | None = None
        self.saved_attrib = {}  # safer way would be to clone lxml tree

    def build_object(self):
        if self.klass is None:
            return
        return self.klass()

    def _restore_attrib(self):
        for el in self.saved_attrib:
            el.attrib.clear()
            el.attrib.update(self.saved_attrib[el])
        self.saved_attrib = {}

    def should_highlight(self) -> bool:
        try:
            responses_dirname = self.page.browser.responses_dirname and self.page.browser.highlight_el
            if not responses_dirname:
                return False
            if not self.el.getroottree():
                return False
        except AttributeError:
            return False
        else:
            return True

    def reroot_element(self, el: Any) -> Any:
        """Reroot a given element for parsing a given object.

        This will be called once the object and environment is set.
        """
        item_xpath = self.item_xpath
        if item_xpath is None:
            # TODO: Remove 'reroot_xpath' references in Woob 4.x, as it has
            # been renamed to 'item_xpath' when merging ItemElementRerootMixin
            # back into ItemElement in 3.6.
            try:
                item_xpath = self.reroot_xpath
            except AttributeError:
                pass
            else:
                # Whether or not it has returned None, it is defined, and is
                # such, should be warned as deprecated.
                warnings.warn(
                    "'reroot_xpath' has been placed into ItemElement "
                    + "and renamed 'item_xpath', please rename the attribute "
                    + "on your side as such; reading this attribute will be "
                    + "removed in Woob 4.0",
                    DeprecationWarning,
                )

        if item_xpath is None:
            return el

        if hasattr(el, 'xpath'):
            return el.xpath(item_xpath)
        elif isinstance(el, (dict, list)):
            return Dict.select(item_xpath.split('/'), self)
        return el

    def _write_highlighted(self):
        if not self.should_highlight():
            return

        responses_dirname = self.page.browser.responses_dirname
        html = lxml.html.tostring(self.el.getroottree().getroot())

        fn = os.path.join(responses_dirname, 'obj-%s.html' % self._random_id)
        with open(fn, 'w') as fd:
            fd.write(html)
        self.logger.debug('highlighted object to %s', fn)

    def __call__(self, obj=None, **kwargs):
        if obj is not None:
            self.obj = obj

        for key, value in kwargs.items():
            self.env[key] = value

        for obj in self:
            return obj

    def __iter__(self):
        original_element = self.el
        self.el = self.reroot_element(original_element)
        try:
            if not self.check_condition():
                return

            highlight = False
            try:
                if self.should_highlight():
                    self.saved_attrib[self.el] = dict(self.el.attrib)
                    self.el.attrib['style'] = 'color: white !important; background: orange !important;'

                try:
                    if self.obj is None:
                        self.obj = self.build_object()
                    self.parse(self.el)
                    self.handle_loaders()
                    for attr in self._attrs:
                        self.handle_attr(attr, getattr(self, 'obj_%s' % attr))
                except SkipItem:
                    return

                if self.validate is not None and not self.validate(self.obj):
                    return

                highlight = True
            finally:
                if highlight:
                    self._write_highlighted()
                self._restore_attrib()
        finally:
            self.el = original_element

        yield self.obj

    def handle_attr(self, key: str, func):
        try:
            value = self.use_selector(func, key=key)
        except SkipItem as e:
            # Help debugging as tracebacks do not give us the key
            self.logger.debug("Attribute %s raises a %r", key, e)
            raise
        except Exception as e:
            # If we are here, we have probably a real parsing issue
            self.logger.warning('Attribute %s (in %s:%s) raises %s', key, self._class_file, self._class_line, repr(e))
            if not self.skip_optional_fields_errors or key not in self.obj._fields or self.obj._fields[key].mandatory:
                raise
            else:
                value = FetchError
        logger = getLogger('woob.browser.b2filters')
        logger.log(DEBUG_FILTERS, "%s.%s = %r" % (self._random_id, key, value))
        setattr(self.obj, key, value)


class ItemElementFromAbstractPageError(Exception):
    pass


class MetaAbstractItemElement(type):
    # hope we get rid of this real fast
    def __new__(mcs, name, bases, dct):
        from woob.tools.backend import Module  # here to avoid file wide circular dependency

        if name != 'ItemElementFromAbstractPage' and ItemElementFromAbstractPage in bases:
            parent_attr = dct.get('BROWSER_ATTR', None)
            if parent_attr:
                m = re.match(r'^[^.]+\.(.*)\.([^.]+)$', parent_attr)
                path, klass_name = m.group(1, 2)
                module = importlib.import_module('woob_modules.%s.%s' % (dct['PARENT'], path))
                browser_klass = getattr(module, klass_name)
            else:
                module = importlib.import_module('woob_modules.%s' % dct['PARENT'])
                for attrname in dir(module):
                    attr = getattr(module, attrname)
                    if isinstance(attr, type) and issubclass(attr, Module) and attr != Module:
                        browser_klass = attr.BROWSER
                        break

            url = getattr(browser_klass, dct['PARENT_URL'])
            page_class = url.klass

            element_class = getattr(page_class, dct['ITER_ELEMENT']).klass
            item_class = element_class.item

            bases = tuple(item_class if isinstance(base, mcs) else base for base in bases)

            return type(name, bases, dct)

        return super().__new__(mcs, name, bases, dct)


class ItemElementFromAbstractPage(metaclass=MetaAbstractItemElement):
    """Don't use this class, import woob_modules.other_module.etc instead"""


class TableElement(ListElement):
    head_xpath = None
    cleaner = CleanText

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._cols = {}

        columns = {}
        for attrname in dir(self):
            m = re.match('col_(.*)', attrname)
            if m:
                cols = getattr(self, attrname)
                if not isinstance(cols, (list,tuple)):
                    cols = [cols]
                columns[m.group(1)] = [s.lower() if isinstance(s, str) else s for s in cols]

        colnum = 0
        for el in self.el.xpath(self.head_xpath):
            title = self.cleaner.clean(el)
            for name, titles in columns.items():
                if name in self._cols:
                    continue
                if title.lower() in [s for s in titles if isinstance(s, str)] or \
                   any(map(lambda x: x.match(title), [s for s in titles if isinstance(s, type(re.compile('')))])):
                    self._cols[name] = colnum
            try:
                colnum += int(el.attrib.get('colspan', 1))
            except (ValueError, AttributeError):
                colnum += 1

    def get_colnum(self, name):
        return self._cols.get(name, None)


class DictElement(ListElement):
    def find_elements(self):
        if self.item_xpath is None:
            selector = []

        elif isinstance(self.item_xpath, str):
            selector = self.item_xpath.split('/')

        else:
            selector = self.item_xpath

        bases = [self.el]
        for key in selector:
            if key == '*':
                bases = sum([el if isinstance(el, list) else list(el.values()) for el in bases], [])
            else:
                bases = [el[int(key)] if isinstance(el, list) else el[key] for el in bases]

        for base in bases:
            if isinstance(base, dict):
                yield from base.values()
            else:
                yield from base


def magic_highlight(els, open_browser=True):
    """Open a web browser with the document open and the element highlighted"""

    import lxml.html
    import webbrowser
    import tempfile

    if not els:
        raise Exception('no elements to highlight')

    if not isinstance(els, (list, tuple)):
        els = [els]

    saved = {}
    for el in els:
        saved[el] = el.attrib.get('style', '')
        el.attrib['style'] = 'color: white !important; background: red !important;'

    html = lxml.html.tostring(el.xpath('/*')[0])
    for el in els:
        el.attrib['style'] = saved[el]

    _, fn = tempfile.mkstemp(prefix='woob-highlight', suffix='.html')
    with open(fn, 'w') as fd:
        fd.write(html)

    print('Saved to %r' % fn)
    if open_browser:
        webbrowser.open('file://%s' % fn)


def __getattr__(name: str) -> Any:
    if name == 'ItemElementRerootMixin':
        warnings.warn(
            'ItemElementRerootMixin is deprecated: rerooting is now '
            + 'allowed with ItemElement directly.',
            DeprecationWarning,
            stacklevel=2,
        )

        class ItemElementRerootMixin:
            """No-op class kept for compatibility.

            This existed because rerooting was only an option with this mixin.
            Since Woob 3.5, rerooting is present in base ItemElement.
            """

        return ItemElementRerootMixin

    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def __dir__() -> list[str]:
    return sorted(list(__all__) + ['ItemElementRerootMixin'])
