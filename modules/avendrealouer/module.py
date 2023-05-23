# -*- coding: utf-8 -*-

# Copyright(C) 2017      ZeHiro
#
# This file is part of a woob module.
#
# This woob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This woob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this woob module. If not, see <http://www.gnu.org/licenses/>.


from woob.tools.backend import Module, BackendConfig
from woob.capabilities.housing import CapHousing, Housing, HousingPhoto
from woob.tools.value import Value
from .browser import AvendrealouerBrowser


__all__ = ['AvendrealouerModule']


class AvendrealouerModule(Module, CapHousing):
    NAME = u'avendrealouer'
    DESCRIPTION = 'avendrealouer website'
    MAINTAINER = 'ZeHiro'
    EMAIL = 'public@abossy.fr'
    LICENSE = 'AGPLv3+'
    VERSION = '3.6'

    BROWSER = AvendrealouerBrowser
    CONFIG = BackendConfig(
        Value('datadome_cookie_search', label='Cookie datadome de la page de recherche', default=''),
        Value('datadome_cookie_detail', label='Cookie datadome de la page de détail', default=''))

    def create_default_browser(self):
        return self.create_browser(self.config['datadome_cookie_search'].get(),
                                   self.config['datadome_cookie_detail'].get())

    def get_housing(self, housing):
        return self.browser.get_housing(housing)

    def search_city(self, pattern):
        return self.browser.get_cities(pattern)

    def search_housings(self, query):
        return self.browser.search_housings(query)

    def fill_housing(self, housing, fields):
        if len(fields) > 0:
            housing = self.browser.get_housing(housing.id)
        return housing

    def fill_photo(self, photo, fields):
        if 'data' in fields and photo.url and not photo.data:
            photo.data = self.browser.open(photo.url).content
        return photo

    OBJECTS = {Housing: fill_housing, HousingPhoto: fill_photo}
