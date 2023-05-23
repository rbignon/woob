# -*- coding: utf-8 -*-

# Copyright(C) 2018 Quentin Defenouillere
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



from woob.capabilities.bands import CapBands, BandNotFound
from woob.tools.backend import Module, BackendConfig
from woob.tools.value import Value, ValueBackendPassword


from .browser import MetalArchivesBrowser

__all__ = ['MetalarchivesModule']

class MetalarchivesModule(Module, CapBands):
    NAME = 'metalarchives'
    DESCRIPTION = 'Metal Archives: Encyclopedia Metallum'
    MAINTAINER = 'Quentin Defenouillère'
    EMAIL = 'quentin.defenouillere@gmail.com'
    LICENSE = 'LGPLv3+'
    VERSION = '3.6'
    BROWSER = MetalArchivesBrowser

    CONFIG = BackendConfig(
        Value('login', label='Metal archives ID'),
        ValueBackendPassword('password', label='Metal archives password')
    )

    def create_default_browser(self, *args, **kwargs):
        return self.create_browser(self.config['login'].get(), self.config['password'].get(), *args, **kwargs)

    # Method to search for a band pattern:
    def iter_band_search(self, pattern):
        bands_list = list(self.browser.iter_band_search(pattern))
        # In case the band search returns no results:
        if not bands_list:
            raise BandNotFound('No band result matched your search query.')
        return bands_list

    # Method to retrieve a band's discography:
    def get_albums(self, id):
        return self.browser.get_albums(id)

    # Method to retrieve a band's information:
    def get_info(self, id):
        return self.browser.get_info(id)

    # Method to retrieve your favorite bands:
    def get_favorites(self):
        return self.browser.get_favorites()

    def suggestions(self):
        favorite_bands = [band.id for band in list(self.get_favorites())]
        return self.browser.suggestions(favorite_bands)
