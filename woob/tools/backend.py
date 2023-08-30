# Copyright(C) 2010-2023 Romain Bignon
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

import logging
import importlib
import os
from copy import copy
from threading import RLock
import warnings
from urllib.request import getproxies
from typing import List, Any, Dict, Tuple, Iterator, Type, ClassVar, TYPE_CHECKING

from packaging.version import Version

from woob import __version__
from woob.capabilities.base import BaseObject, Capability, FieldNotFound, NotAvailable, NotLoaded
from woob.tools.json import json
from woob.tools.log import getLogger
from woob.tools.misc import iter_fields
from woob.tools.storage import IStorage
from woob.tools.value import ValuesDict, ValueBool

if TYPE_CHECKING:
    from woob.core import WoobBase
    from woob.browser import Browser


__all__ = ['BackendStorage', 'BackendConfig', 'Module']


class BackendStorage:
    """
    This is an abstract layer to store data in storages (:mod:`woob.tools.storage`)
    easily.

    It is instancied automatically in constructor of :class:`Module`, in the
    :attr:`Module.storage` attribute.

    :param name: name of backend
    :type name: str
    :param storage: storage object
    :type storage: :class:`woob.tools.storage.IStorage`
    """

    def __init__(self, name: str, storage: IStorage | None):
        self.name = name
        self.storage = storage

    def set(self, *args):
        """
        Set value in the storage.

        Example:

        >>> from woob.tools.storage import StandardStorage
        >>> backend = BackendStorage('blah', StandardStorage('/tmp/cfg'))
        >>> backend.storage.set('config', 'nb_of_threads', 10)  # doctest: +SKIP
        >>>

        :param args: the path where to store value
        """
        if self.storage:
            self.storage.set('backends', self.name, *args)

    def delete(self, *args):
        """
        Delete a value from the storage.

        :param args: path to delete.
        """
        if self.storage:
            self.storage.delete('backends', self.name, *args)

    def get(self, *args, **kwargs) -> Any:
        """
        Get a value or a dict of values in storage.

        Example:

        >>> from woob.tools.storage import StandardStorage
        >>> backend = BackendStorage('blah', StandardStorage('/tmp/cfg'))
        >>> backend.storage.get('config', 'nb_of_threads')  # doctest: +SKIP
        10
        >>> backend.storage.get('config', 'unexistant', 'path', default='lol')  # doctest: +SKIP
        'lol'
        >>> backend.storage.get('config')  # doctest: +SKIP
        {'nb_of_threads': 10, 'other_things': 'blah'}

        :param args: path to get
        :param default: if specified, default value when path is not found
        """
        if self.storage:
            return self.storage.get('backends', self.name, *args, **kwargs)

        return kwargs.get('default', None)

    def load(self, default: Dict):
        """
        Load storage.

        It is made automatically when your backend is created, and use the
        ``STORAGE`` class attribute as default.

        :param default: this is the default tree if storage is empty
        :type default: :class:`dict`
        """
        if self.storage:
            self.storage.load('backends', self.name, default)

    def save(self):
        """
        Save storage.
        """
        if self.storage:
            self.storage.save('backends', self.name)


class BackendConfig(ValuesDict):
    """
    Configuration of a backend.

    This class is firstly instanced as a :class:`woob.tools.value.ValuesDict`,
    containing some :class:`woob.tools.value.Value` (and derivated) objects.

    Then, using the :func:`load` method will load configuration from file and
    create a copy of the :class:`BackendConfig` object with the loaded values.
    """
    modname: str
    instname: str
    woob: WoobBase

    def load(
        self,
        woob: WoobBase,
        modname: str,
        instname: str,
        config: Dict,
        nofail: bool = False
    ) -> BackendConfig:
        """
        Load configuration from dict to create an instance.

        :param woob: woob object
        :type woob: :class:`woob.core.woob.WoobBase`
        :param modname: name of the module
        :type modname: :class:`str`
        :param instname: name of this backend
        :type instname: :class:`str`
        :param params: parameters to load
        :type params: :class:`dict`
        :param nofail: if true, this call can't fail
        :type nofail: :class:`bool`
        :rtype: :class:`BackendConfig`
        """
        cfg = self.__class__()
        cfg.modname = modname
        cfg.instname = instname
        cfg.woob = woob
        for name, field in self.items():
            value = config.get(name, None)

            if value is None:
                if not nofail and field.required:
                    raise Module.ConfigError(
                        f'Backend({cfg.instname}): Configuration error: Missing parameter {name} ({field.description})',
                       bad_fields=[name]
                    )
                value = field.default

            field = copy(field)
            try:
                field.load(cfg.instname, value, cfg.woob.requests)
            except ValueError as v:
                if not nofail:
                    raise Module.ConfigError(
                        f'Backend({cfg.instname}): Configuration error for field "{name}": {v}',
                        bad_fields=[name]
                    )

            cfg[name] = field
        return cfg

    def dump(self) -> dict:
        """
        Dump config in a dictionary.

        :rtype: :class:`dict`
        """
        settings = {}
        for name, value in self.items():
            if not value.transient:
                settings[name] = value.dump()
        return settings

    def save(self, edit: bool = True, params: Dict | None = None):
        """
        Save backend config.

        :param edit: if true, it changes config of an existing backend
        :type edit: :class:`bool`
        :param params: if supplied, params to merge with the ones of the current object
        :type params: :class:`dict`
        """
        assert self.modname is not None
        assert self.instname is not None
        assert self.woob is not None

        dump = self.dump()
        if params is not None:
            dump.update(params)

        if edit:
            self.woob.backends_config.edit_backend(self.instname, dump)
        else:
            self.woob.backends_config.add_backend(self.instname, self.modname, dump)


class Module:
    """
    Base class for modules.

    You may derivate it, and also all capabilities you want to implement.

    :param woob: woob instance
    :type woob: :class:`woob.core.woob.Woob`
    :param name: name of backend
    :type name: :class:`str`
    :param config: configuration of backend (optional)
    :type config: :class:`dict`
    :param storage: storage object (optional)
    :type storage: :class:`woob.tools.storage.IStorage`
    :param logger: parent logger (optional)
    :type logger: :class:`logging.Logger`
    """

    NAME: ClassVar[str]
    """Name of the maintainer of this module."""

    MAINTAINER: ClassVar[str] = '<unspecified>'
    """Name of the maintainer."""

    EMAIL: ClassVar[str] = '<unspecified>'
    """Email address of the maintainer."""

    DESCRIPTION: ClassVar[str] = '<unspecified>'
    """Description"""

    LICENSE: ClassVar[str] = '<unspecified>'
    """License of the module"""

    CONFIG: ClassVar[BackendConfig] = BackendConfig()
    """Configuration required for backends.

    Values must be :class:`woob.tools.value.Value` objects.
    """

    STORAGE: ClassVar[Dict] = {}
    """Storage"""

    BROWSER: Browser | None = None
    """Browser class"""

    ICON: ClassVar[str | None] = None
    """URL to an optional icon.

    If you want to create your own icon, create a 'favicon.png' icon in
    the module's directory, and keep the ICON value to None.
    """

    OBJECTS: ClassVar[Dict] = {}
    """Supported objects to fill

    The key is the class and the value the method to call to fill
    Method prototype: method(object, fields)
    When the method is called, fields are only the one which are
    NOT yet filled.
    """

    DEPENDENCIES: ClassVar[Tuple[str]] = ()
    """Tuple of module names on which this module depends."""

    class ConfigError(Exception):
        """
        Raised when the config can't be loaded.
        """

        def __init__(self, message, bad_fields=None):
            """
            :type message: str
            :param message: message of the exception
            :type bad_fields: list[str]
            :param bad_fields: names of the config fields which are incorrect
            """

            super().__init__(message)
            self.bad_fields = bad_fields or ()

    def __enter__(self):
        self.lock.acquire()

    def __exit__(self, t, v, tb):
        self.lock.release()

    def __repr__(self):
        return f"<Backend {self.name}>"

    def __new__(cls, *args, **kwargs):
        """ Accept any arguments, necessary for AbstractModule __new__ override.

        AbstractModule, in its overridden __new__, removes itself from class hierarchy
        so its __new__ is called only once. In python 3, default (object) __new__ is
        then used for next instantiations but it's a slot/"fixed" version supporting
        only one argument (type to instanciate).
        """
        return object.__new__(cls)

    @property
    def VERSION(self):
        warnings.warn(
            'Attribute Module.VERSION will be removed in woob 4, do not use it.',
            DeprecationWarning,
            stacklevel=3
        )
        return Version(__version__).base_version

    def __init__(
        self,
        woob: WoobBase,
        name: str,
        config: Dict | None = None,
        storage: IStorage | None = None,
        logger: logging.Logger | None = None,
        nofail: bool = False
    ):
        if (
            hasattr(self.__class__, 'VERSION') and
            not isinstance(self.__class__.VERSION, property)
        ):
            warnings.warn(
                f'Class attribute {self.__class__.__name__}.VERSION is now '
                'unused and deprecated, you can remove it. '
                'If you do so, do not forget to increase the woob version to at '
                'least 3.4 in requirements.txt.',
                DeprecationWarning,
            )

        self.logger = getLogger(name, parent=logger)
        self.woob = woob
        self.name = name
        self.lock = RLock()
        if config is None:
            config = {}

        # Private fields (which start with '_')
        self._private_config = dict((key, value) for key, value in config.items() if key.startswith('_'))

        # Load configuration of backend.
        self.config = self.CONFIG.load(woob, self.NAME, self.name, config, nofail)

        self.storage = BackendStorage(self.name, storage)
        self.storage.load(self.STORAGE)

    def dump_state(self):
        """
        Dump module state into storage.
        """
        if hasattr(self.browser, 'dump_state'):
            self.storage.set('browser_state', self.browser.dump_state())
            self.storage.save()

    def deinit(self):
        """
        This abstract method is called when the backend is unloaded.
        """
        if self._browser is None:
            return

        try:
            self.dump_state()
        finally:
            if hasattr(self.browser, 'deinit'):
                self.browser.deinit()

    @property
    def weboob(self):
        """
        .. deprecated:: 3.4
           Don't use this attribute, but :attr:`woob` instead.
        """
        warnings.warn('Use Module.woob instead.', DeprecationWarning, stacklevel=2)
        return self.woob

    _browser = None

    @property
    def browser(self) -> Browser:
        """
        Attribute 'browser'. The browser is created at the first call
        of this attribute, to avoid useless pages access.

        Note that the :func:`create_default_browser` method is called to create it.
        """
        if self._browser is None:
            self._browser = self.create_default_browser()
        return self._browser

    def create_default_browser(self) -> Browser | None:
        """
        Method to overload to build the default browser in
        attribute 'browser'.
        """
        return self.create_browser()

    def create_browser(self, *args, **kwargs) -> Browser | None:
        """
        Build a browser from the BROWSER class attribute and the
        given arguments.

        :param klass: optional parameter to give another browser class to instanciate
        :type klass: :class:`woob.browser.browsers.Browser`
        :param load_state: Whether to load the browser state if it supports
            the feature.
        :type load_state: bool
        """

        klass = kwargs.pop('klass', self.BROWSER)
        if not klass:
            return None

        should_load_state = bool(kwargs.pop('load_state', True))

        kwargs['proxy'] = self.get_proxy()
        if '_proxy_headers' in self._private_config:
            kwargs['proxy_headers'] = self._private_config['_proxy_headers']
            if isinstance(kwargs['proxy_headers'], str):
                kwargs['proxy_headers'] = json.loads(kwargs['proxy_headers'])

        if '_ssl_verify' in self._private_config:
            # value can be either a boolean or a string (path)
            value = ValueBool()
            try:
                value.set(self._private_config['_ssl_verify'])
            except ValueError:
                kwargs.setdefault('verify', self._private_config['_ssl_verify'])
            else:
                kwargs.setdefault('verify', value.get())

        kwargs['logger'] = self.logger

        if self.logger.settings['responses_dirname']:
            kwargs.setdefault('responses_dirname', os.path.join(self.logger.settings['responses_dirname'],
                                                                self._private_config.get('_debug_dir', self.name)))
        elif os.path.isabs(self._private_config.get('_debug_dir', '')):
            kwargs.setdefault('responses_dirname', self._private_config['_debug_dir'])

        if '_highlight_el' in self._private_config:
            value = ValueBool()
            try:
                value.set(self._private_config['_highlight_el'])
            except ValueError as e:
                raise Module.ConfigError(
                    f'Backend({self.name}): Configuration error: _highlight_el must be a boolean'
                ) from e

            kwargs.setdefault('highlight_el', value.get())

        browser = klass(*args, **kwargs)

        if should_load_state and hasattr(browser, 'load_state'):
            browser.load_state(self.storage.get('browser_state', default={}))

        return browser

    def get_proxy(self) -> Dict[str, str]:
        """
        Get proxy to use.

        It will read in environment variables, then in backend config.

        Proxy keys in backend config are:

        * ``_proxy`` for HTTP requests
        * ``_proxy_ssl`` for HTTPS requests
        """
        # Get proxies from environment variables
        proxies = getproxies()
        # Override them with backend-specific config
        if '_proxy' in self._private_config:
            proxies['http'] = self._private_config['_proxy']
        if '_proxy_ssl' in self._private_config:
            proxies['https'] = self._private_config['_proxy_ssl']
        # Remove empty values
        for key in list(proxies.keys()):
            if not proxies[key]:
                del proxies[key]
        return proxies

    @classmethod
    def iter_caps(cls) -> Iterator[Type[Capability]]:
        """
        Iter capabilities implemented by this backend.

        :rtype: iter[:class:`woob.capabilities.base.Capability`]
        """
        for base in cls.mro():
            if issubclass(base, Capability) and base != Capability and base != cls and not issubclass(base, Module):
                yield base

    def has_caps(self, *caps) -> bool:
        """
        Check if this backend implements at least one of these capabilities.

        `caps` should be list of :class:`Capability` objects (e.g. :class:`CapBank`) or capability names (e.g. 'bank').
        """
        available_cap_names = [cap.__name__ for cap in self.iter_caps()]
        return any(
            (isinstance(c, str) and c in available_cap_names) or isinstance(self, c)
            for c in caps
        )

    def fillobj(self, obj: BaseObject, fields: List[str] | None = None):
        """
        Fill an object with the wanted fields.

        :param fields: what fields to fill; if None, all fields are filled
        :type fields: :class:`list`
        """
        if obj is None:
            return obj

        def not_loaded_or_incomplete(v):
            return (v is NotLoaded or isinstance(v, BaseObject) and not v.__iscomplete__())

        def not_loaded(v):
            return v is NotLoaded

        def filter_missing_fields(obj, fields, check_cb):
            missing_fields = []
            if fields is None:
                # Select all fields
                if isinstance(obj, BaseObject):
                    fields = [item[0] for item in obj.iter_fields()]
                else:
                    fields = [item[0] for item in iter_fields(obj)]

            for field in fields:
                if not hasattr(obj, field):
                    raise FieldNotFound(obj, field)
                value = getattr(obj, field)

                missing = False
                if hasattr(value, '__iter__'):
                    for v in (value.values() if isinstance(value, dict) else value):
                        if check_cb(v):
                            missing = True
                            break
                elif check_cb(value):
                    missing = True

                if missing:
                    missing_fields.append(field)

            return missing_fields

        if isinstance(fields, str):
            fields = (fields,)

        missing_fields = filter_missing_fields(obj, fields, not_loaded_or_incomplete)

        if not missing_fields:
            return obj

        for key, value in self.OBJECTS.items():
            if isinstance(obj, key):
                self.logger.debug('Fill %r with fields: %s', obj, missing_fields)
                obj = value(self, obj, missing_fields) or obj
                break

        missing_fields = filter_missing_fields(obj, fields, not_loaded)

        # Object is not supported by backend. Do not notice it to avoid flooding user.
        # That's not so bad.
        for field in missing_fields:
            setattr(obj, field, NotAvailable)

        return obj


class AbstractModuleMissingParentError(Exception):
    pass


class MetaModule(type):
    # we can remove this class as soon as we get rid of Abstract*
    def __new__(mcs, name, bases, dct):
        if name != 'AbstractModule' and AbstractModule in bases:
            warnings.warn('AbstractModule is deprecated and will be removed in woob 4.0. '
                          'Use standard "from woob_modules.other_module import Module" instead.',
                          DeprecationWarning, stacklevel=2)

            module = importlib.import_module('woob_modules.%s' % dct['PARENT'])
            symbols = [getattr(module, attr) for attr in dir(module) if not attr.startswith('__')]
            klass = next(
                symbol for symbol in symbols
                if isinstance(symbol, type) and issubclass(symbol, Module) and symbol != Module
            )

            bases = tuple(klass if isinstance(base, mcs) else base for base in bases)

            additional_config = dct.pop('ADDITIONAL_CONFIG', None)
            if additional_config:
                dct['CONFIG'] = BackendConfig(*(list(klass.CONFIG.values()) + list(additional_config.values())))

        return super().__new__(mcs, name, bases, dct)


class AbstractModule(metaclass=MetaModule):
    """
    .. deprecated:: 3.4
       Don't use this class, import woob_modules.other_module.etc instead
    """
