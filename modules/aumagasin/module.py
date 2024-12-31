# Copyright(C) 2023      Bezleputh
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
# along with this woob module. If not, see <http://www.gnu.org/licenskes/>.


from woob.capabilities.contact import CapDirectory
from woob.tools.backend import Module

from .browser import AumagasinBrowser


__all__ = ['AumagasinModule']


class AumagasinModule(Module, CapDirectory):
    NAME = 'aumagasin'
    DESCRIPTION = 'Liste des magasins de France'
    MAINTAINER = 'Bezleputh'
    EMAIL = 'carton_ben@yahoo.fr'
    LICENSE = 'LGPLv3+'

    BROWSER = AumagasinBrowser

    def search_contacts(self, query, sortby):
        """
        Search contacts matching a query.

        :param query: search parameters
        :type query: :class:`SearchQuery`
        :rtype: iter[:class:`PhysicalEntity`]
        """
        return self.browser.search_contacts(query)
