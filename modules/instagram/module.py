# -*- coding: utf-8 -*-

# Copyright(C) 2020      Vincent A
#
# This file is part of a woob module.
#
# This woob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This woob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this woob module. If not, see <http://www.gnu.org/licenses/>.

# flake8: compatible

from __future__ import unicode_literals

from weboob.tools.backend import Module, BackendConfig
from weboob.tools.value import Value
from weboob.capabilities.image import CapImage, BaseImage, Thumbnail
from weboob.capabilities.collection import CapCollection

from .browser import InstagramBrowser


__all__ = ['InstagramModule']


class InstagramModule(Module, CapImage, CapCollection):
    NAME = 'instagram'
    DESCRIPTION = 'Instagram'
    MAINTAINER = 'Vincent A'
    EMAIL = 'dev@indigo.re'
    LICENSE = 'LGPLv3+'
    VERSION = '2.1'

    BROWSER = InstagramBrowser

    CONFIG = BackendConfig(
        Value('user')
    )

    def create_default_browser(self):
        return self.create_browser(self.config['user'].get())

    def iter_resources(self, types, split_path):
        for type in types:
            if issubclass(type, BaseImage):
                yield from self.browser.iter_images()
                break

    def fill_img(self, img, fields):
        if 'data' in fields and img.url:
            img.data = self.browser.open(img.url).content

    OBJECTS = {
        BaseImage: fill_img,
        Thumbnail: fill_img,
    }
