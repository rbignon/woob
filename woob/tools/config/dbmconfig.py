# Copyright(C) 2016-2021 Edouard Lefebvre du Prey
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


import dbm.ndbm
import yaml

from .iconfig import ConfigError, IConfig
from .yamlconfig import WoobDumper




__all__ = ['DBMConfig']


class DBMConfig(IConfig):
    def __init__(self, path):
        self.path = path
        self.storage = None

    def load(self, default=None):
        self.storage = dbm.ndbm.open(self.path, 'c')

    def save(self):
        if hasattr(self.storage, 'sync'):
            self.storage.sync()

    def get(self, *args, **kwargs):
        key = '.'.join(args)
        try:
            value = self.storage[key]
            value = yaml.load(value, Loader=yaml.SafeLoader)
        except KeyError as exc:
            if 'default' in kwargs:
                value = kwargs.get('default')
            else:
                raise ConfigError() from exc
        except TypeError as exc:
            raise ConfigError() from exc
        return value

    def set(self, *args):
        key = '.'.join(args[:-1])
        value = args[-1]
        try:
            self.storage[key] = yaml.dump(value, None, Dumper=WoobDumper, default_flow_style=False)
        except KeyError as exc:
            raise ConfigError() from exc
        except TypeError as exc:
            raise ConfigError() from exc

    def delete(self, *args):
        key = '.'.join(args)
        try:
            del self.storage[key]
        except KeyError as exc:
            raise ConfigError() from exc
        except TypeError as exc:
            raise ConfigError() from exc
