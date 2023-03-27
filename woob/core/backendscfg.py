# Copyright(C) 2010-2011 Romain Bignon
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

import codecs
import os
import stat
import sys
from collections.abc import MutableMapping
from configparser import RawConfigParser, DuplicateSectionError
from logging import warning
from subprocess import check_output, CalledProcessError
from typing import Iterator, Tuple


__all__ = ['BackendsConfig', 'BackendAlreadyExists']


class BackendAlreadyExists(Exception):
    """
    Try to add a backend that already exists.
    """


class DictWithCommands(MutableMapping):
    def __init__(self, *args, **kwargs):
        super().__init__()
        self._raw = dict(*args, **kwargs)

    def __getitem__(self, key):
        value = self._raw[key]
        if value.startswith('`') and value.endswith('`'):
            try:
                value = check_output(value[1:-1], shell=True)  # nosec: this is intended
            except CalledProcessError as e:
                raise ValueError(f'The call to the external tool failed: {e}') from e

            value = value.decode('utf-8').partition('\n')[0].strip('\r\n\t')

        return value

    def __setitem__(self, key, value):
        self._raw[key] = value

    def __delitem__(self, key):
        del self._raw[key]

    def __len__(self):
        return len(self._raw)

    def __iter__(self):
        return iter(self._raw)


class BackendsConfig:
    """
    Config of backends.

    A backend is an instance of a module with a config.
    A module can therefore have multiple backend instances.

    :param confpath: path to the backends config file
    :type confpath: str
    """

    class WrongPermissions(Exception):
        """
        Unable to write in the backends config file.
        """

    def __init__(self, confpath: str):
        self.confpath = confpath
        try:
            mode = os.stat(confpath).st_mode
        except OSError:
            if not os.path.isdir(os.path.dirname(confpath)):
                os.makedirs(os.path.dirname(confpath))
            if sys.platform == 'win32':
                fptr = open(confpath, 'w', encoding='utf-8')
                fptr.close()
            else:
                try:
                    fd = os.open(confpath, os.O_WRONLY | os.O_CREAT, 0o600)
                    os.close(fd)
                except OSError:
                    fptr = open(confpath, 'w', encoding='utf-8')
                    fptr.close()
                    os.chmod(confpath, 0o600)
        else:
            if sys.platform != 'win32':
                if mode & stat.S_IRGRP or mode & stat.S_IROTH:
                    raise self.WrongPermissions(
                        f'Woob will not start as long as config file {confpath} is readable by group or other users.'
                    )

    def _read_config(self):
        config = RawConfigParser()
        with codecs.open(self.confpath, 'r', encoding='utf-8') as fd:
            config.read_file(fd, self.confpath)
        return config

    def _write_config(self, config):
        f = codecs.open(self.confpath, 'wb', encoding='utf-8')
        with f:
            config.write(f)

    def iter_backends(self) -> Iterator[Tuple[str, str, DictWithCommands]]:
        """
        Iter on all saved backends.

        An item is a tuple with backend name, module name, and params dict.
        """
        config = self._read_config()
        changed = False
        for backend_name in config.sections():
            params = DictWithCommands(config.items(backend_name))
            try:
                module_name = params.pop('_module')
            except KeyError:
                warning('Missing field "_module" for configured backend "%s"', backend_name)
                continue
            yield backend_name, module_name, params

        if changed:
            self._write_config(config)

    def backend_exists(self, name: str) -> bool:
        """
        Return True if the backend exists in config.
        """
        config = self._read_config()
        return name in config.sections()

    def add_backend(self, backend_name: str, module_name: str, params: dict):
        """
        Add a backend to config.

        :param backend_name: name of the backend in config
        :type backend_name: str
        :param module_name: name of woob module
        :type module_name: str
        :param params: params of the backend
        :type params: dict
        """
        if not backend_name:
            raise ValueError('Please give a name to the configured backend.')
        config = self._read_config()
        try:
            config.add_section(backend_name)
        except DuplicateSectionError as exc:
            raise BackendAlreadyExists(backend_name) from exc

        config.set(backend_name, '_module', module_name)
        for key, value in params.items():
            config.set(backend_name, key, value)

        self._write_config(config)

    def edit_backend(self, backend_name: str, params: dict):
        """
        Edit a backend in config.

        :param backend_name: name of the backend in config
        :param params: params to change
        :type params: :class:`dict`
        """
        config = self._read_config()
        if not config.has_section(backend_name):
            raise KeyError(f'Configured backend "{backend_name}" not found')

        for key, value in params.items():
            config.set(backend_name, key, value)

        self._write_config(config)

    def get_backend(self, backend_name: str) -> Tuple[str, dict]:
        """
        Get options of backend.

        :returns: a tuple with the module name and the backends params
        :rtype: tuple[str, dict]
        """

        config = self._read_config()
        if not config.has_section(backend_name):
            raise KeyError(f'Configured backend "{backend_name}" not found')

        # XXX why not a DictWithCommands?
        items = dict(config.items(backend_name))

        try:
            module_name = items.pop('_module')
        except KeyError:
            warning('Missing field "_module" for configured backend "%s"', backend_name)
            raise KeyError(f'Configured backend "{backend_name}" not found')

        return module_name, items

    def remove_backend(self, backend_name: str) -> bool:
        """
        Remove a backend from config.

        Returns False if the backend does not exist.
        """
        config = self._read_config()
        if not config.remove_section(backend_name):
            return False
        self._write_config(config)
        return True
