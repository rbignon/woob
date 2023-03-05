# -*- coding: utf-8 -*-

# Copyright(C) 2019      Guntra
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
from woob.capabilities.housing import CapHousing
from .browser import LesterrainsBrowser


# Some remarks:
# - post type is hardcoded as POSTS_TYPES.SALE because it makes sense here to have it fixed
# - advert is hardcoded as ADVERT_TYPES.PROFESSIONAL (same)
# - house type is hardcoded as HOUSE_TYPES.LAND (same)
# - Only the first city in the query is taken into account for now (work in progress)
# - If a post has multiple lands, we choose the lowest cost and the highest area to have the best match.
#   You'll have to review manually the lands of course and see if there is a good combo cost/area.
#   So don't be too happy if you see a cheap big land ;)

__all__ = ['LesterrainsModule']


class LesterrainsModule(Module, CapHousing):
    NAME = 'lesterrains'
    DESCRIPTION = 'Les-Terrains.com'
    MAINTAINER = 'Guntra'
    EMAIL = 'guntra@example.com'
    LICENSE = 'LGPLv3+'
    VERSION = '3.4'
    BROWSER = LesterrainsBrowser

    def search_city(self, pattern):
        return self.browser.get_cities(pattern)

    def search_housings(self, query):
        cities = ['%s' % c.id for c in query.cities if c.backend == self.name]
        if len(cities) == 0:
            return list()
        return self.browser.search_housings(
            cities,
            query.area_min,
            query.area_max,
            query.cost_min,
            query.cost_max
        )

    def get_housing(self, housing):
        return self.browser.get_housing(housing)
