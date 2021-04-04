# -*- coding: utf-8 -*-

# Copyright(C) 2017      Vincent A
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

from woob.tools.backend import Module
from woob.capabilities.file import CapFile
from woob.capabilities.image import CapImage, BaseImage

from .browser import UnsplashBrowser


__all__ = ['UnsplashModule']


class UnsplashModule(Module, CapImage):
    NAME = 'unsplash'
    DESCRIPTION = u'unsplash website'
    MAINTAINER = u'Vincent A'
    EMAIL = 'dev@indigo.re'
    LICENSE = 'AGPLv3+'
    VERSION = '2.1'

    BROWSER = UnsplashBrowser

    def search_image(self, pattern, sortby=CapFile.SEARCH_RELEVANCE, nsfw=False):
        return self.browser.search_image(pattern)

    def fill_image(self, img, fields):
        if 'data' in fields:
            img.data = self.browser.open(img.url).content
        if 'thumbnail' in fields:
            img.thumbnail.data = self.browser.open(img.thumbnail.url).content

    OBJECTS = {BaseImage: fill_image}
