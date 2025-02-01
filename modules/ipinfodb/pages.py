# -*- coding: utf-8 -*-

# Copyright(C) 2015-2016 Julien Veyssier
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


from woob.browser.elements import ItemElement, method
from woob.browser.filters.standard import CleanText, Regexp, Type
from woob.browser.pages import HTMLPage
from woob.capabilities.base import NotAvailable
from woob.capabilities.geolocip import IpLocation


class LocationPage(HTMLPage):
    @method
    class get_location(ItemElement):
        klass = IpLocation

        obj_id = Regexp(CleanText('//h1/strong[starts-with(.,"IP Address Information")]'), r"- ([.\d]+)")

        obj_city = CleanText('//td[.//strong[text()="City"]]', children=False)
        obj_country = CleanText('//td[.//strong[text()="Country"]]', children=False)
        obj_region = CleanText('//td[.//strong[text()="Region"]]', children=False)
        obj_zipcode = CleanText('//td[.//strong[text()="Postcode"]]', children=False)
        obj_host = CleanText('//td[.//strong[text()="Domain Name"]]', children=False, default=NotAvailable)
        obj_isp = CleanText('//td[.//strong[text()="ISP"]]', children=False)
        obj_lt = Regexp(
            CleanText('//td[.//strong[text()="Coordinates of City"]]', children=False), r"\(([\d.-]+), [\d.-]+\)"
        ) & Type(type=float)
        obj_lg = Regexp(
            CleanText('//td[.//strong[text()="Coordinates of City"]]', children=False), r"\([\d.-]+, ([\d.-]+)\)"
        ) & Type(type=float)
