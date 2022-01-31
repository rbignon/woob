# -*- coding: utf-8 -*-

# Copyright(C) 2010-2013 Romain Bignon
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

import importlib
import logging
import pkgutil
import sys

from woob.tools.backend import Module
from woob.tools.log import getLogger
from woob.exceptions import ModuleLoadError

__all__ = ['LoadedModule', 'ModulesLoader', 'RepositoryModulesLoader']


class LoadedModule(object):
    def __init__(self, package):
        self.logger = getLogger('woob.backend')
        self.package = package
        self.klass = None
        for attrname in dir(self.package):
            attr = getattr(self.package, attrname)
            if isinstance(attr, type) and issubclass(attr, Module) and attr != Module:
                self.klass = attr
        if not self.klass:
            raise ImportError('%s is not a backend (no Module class found)' % package)

    @property
    def name(self):
        return self.klass.NAME

    @property
    def maintainer(self):
        return u'%s <%s>' % (self.klass.MAINTAINER, self.klass.EMAIL)

    @property
    def version(self):
        return self.klass.VERSION

    @property
    def description(self):
        return self.klass.DESCRIPTION

    @property
    def license(self):
        return self.klass.LICENSE

    @property
    def config(self):
        return self.klass.CONFIG

    @property
    def website(self):
        if self.klass.BROWSER and hasattr(self.klass.BROWSER, 'BASEURL') and self.klass.BROWSER.BASEURL:
            return self.klass.BROWSER.BASEURL
        if self.klass.BROWSER and hasattr(self.klass.BROWSER, 'DOMAIN') and self.klass.BROWSER.DOMAIN:
            return '%s://%s' % (self.klass.BROWSER.PROTOCOL, self.klass.BROWSER.DOMAIN)
        else:
            return None

    @property
    def icon(self):
        return self.klass.ICON

    @property
    def dependencies(self):
        return self.klass.DEPENDENCIES

    def iter_caps(self):
        return self.klass.iter_caps()

    def has_caps(self, *caps):
        """Return True if module implements at least one of the caps."""
        for c in caps:
            if (isinstance(c, str) and c in [cap.__name__ for cap in self.iter_caps()]) or \
               (type(c) == type and issubclass(self.klass, c)):
                return True
        return False

    def create_instance(self, woob, backend_name, config, storage, nofail=False, logger=None):
        backend_instance = self.klass(woob, backend_name, config, storage, logger=logger or self.logger, nofail=nofail)
        self.logger.debug(u'Created backend "%s" for module "%s"' % (backend_name, self.name))
        return backend_instance


def _add_in_modules_path(path):
    try:
        import woob_modules
    except ImportError:
        from types import ModuleType

        woob_modules = ModuleType('woob_modules')
        sys.modules['woob_modules'] = woob_modules

        woob_modules.__path__ = [path]
    else:
        if path not in woob_modules.__path__:
            woob_modules.__path__.append(path)


class ModulesLoader(object):
    """
    Load modules.
    """

    def __init__(self, path=None, version=None):
        self.version = version
        self.path = path
        if self.path:
            _add_in_modules_path(self.path)
        self.loaded = {}
        self.logger = getLogger("%s.loader" % __name__)

    def get_or_load_module(self, module_name):
        """
        Can raise a ModuleLoadError exception.
        """
        if module_name not in self.loaded:
            self.load_module(module_name)
        return self.loaded[module_name]

    def iter_existing_module_names(self):
        try:
            import woob_modules
        except ImportError:
            return

        for module in pkgutil.iter_modules(woob_modules.__path__):
            yield module.name

    def module_exists(self, name):
        for existing_module_name in self.iter_existing_module_names():
            if existing_module_name == name:
                return True
        return False

    def load_all(self):
        for existing_module_name in self.iter_existing_module_names():
            try:
                self.load_module(existing_module_name)
            except ModuleLoadError as e:
                self.logger.warning('could not load module %s: %s', existing_module_name, e)

    def load_module(self, module_name):
        module_path = self.get_module_path(module_name)

        if module_name in self.loaded:
            self.logger.debug('Module "%s" is already loaded from %s', module_name, module_path)
            return

        _add_in_modules_path(module_path)

        try:
            pymodule = importlib.import_module('woob_modules.%s' % module_name)
            module = LoadedModule(pymodule)
        except Exception as e:
            if logging.root.level <= logging.DEBUG:
                self.logger.exception(e)
            raise ModuleLoadError(module_name, e)

        if module.version != self.version:
            raise ModuleLoadError(module_name, "Module requires Woob %s, but you use Woob %s. Hint: use 'woob config update'"
                                               % (module.version, self.version))

        self.loaded[module_name] = module
        self.logger.debug('Loaded module "%s" from %s' % (module_name, module.package.__path__[0]))

    def get_module_path(self, module_name):
        return self.path


class RepositoryModulesLoader(ModulesLoader):
    """
    Load modules from repositories.
    """

    def __init__(self, repositories):
        super(RepositoryModulesLoader, self).__init__(repositories.modules_dir, repositories.version)
        self.repositories = repositories
        # repositories.modules_dir is ...../woob_modules
        # shouldn't be in sys.path, its parent should
        # or we add it in woob_modules.__path__
        # sys.path.append(os.path.dirname(repositories.modules_dir))

    def iter_existing_module_names(self):
        for name in self.repositories.get_all_modules_info():
            yield name

    def get_module_path(self, module_name):
        minfo = self.repositories.get_module_info(module_name)
        if minfo is None:
            raise ModuleLoadError(module_name, 'No such module %s' % module_name)
        if minfo.path is None:
            raise ModuleLoadError(module_name, 'Module %s is not installed' % module_name)

        return minfo.path
