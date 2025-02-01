# Copyright(C) 2018      Antoine BOSSY
#
# This file is part of woob.
#
# woob is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# woob is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with woob. If not, see <http://www.gnu.org/licenses/>.


from woob.capabilities.housing import CapHousing, Housing, HousingPhoto
from woob.tools.backend import Module

from .browser import BieniciBrowser


__all__ = ["BieniciModule"]


class BieniciModule(Module, CapHousing):
    NAME = "bienici"
    DESCRIPTION = "bienici website"
    MAINTAINER = "Antoine BOSSY"
    EMAIL = "mail+github@abossy.fr"
    LICENSE = "AGPLv3+"
    VERSION = "3.7"

    BROWSER = BieniciBrowser

    def get_housing(self, id, housing=None):
        """
        Get an housing from an ID.

        :param housing: ID of the housing
        :type housing: str
        :rtype: :class:`Housing` or None if not found.
        """
        return self.browser.get_housing(id, housing)

    def search_city(self, pattern):
        """
        Search a city from a pattern.

        :param pattern: pattern to search
        :type pattern: str
        :rtype: iter[:class:`City`]
        """
        return self.browser.get_cities(pattern)

    def search_housings(self, query):
        """
        Search housings.

        :param query: search query
        :type query: :class:`Query`
        :rtype: iter[:class:`Housing`]
        """
        return self.browser.search_housing(query)

    def fill_photo(self, photo, fields):
        """
        Fills the photo.
        """
        if "data" in fields and photo.url and not photo.data:
            photo.data = self.browser.open(photo.url).content
        return photo

    def fill_housing(self, housing, fields):
        """
        Fills the housing.
        """
        if "phone" in fields:
            housing = self.get_housing(housing.id, housing)
        if "station" in fields and housing._id_polygone:
            housing.station = self.browser.get_stations(housing._id_polygone)
        return housing

    OBJECTS = {HousingPhoto: fill_photo, Housing: fill_housing}
