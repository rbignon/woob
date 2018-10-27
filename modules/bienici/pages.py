# -*- coding: utf-8 -*-

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

from __future__ import unicode_literals


from woob.browser.pages import JsonPage
from woob.browser.elements import ItemElement, DictElement, method
from woob.browser.filters.json import Dict, ItemNotFound
from woob.capabilities.base import NotAvailable
from woob.browser.filters.standard import CleanText, Date, CleanDecimal
from woob.capabilities.housing import City, Housing, HousingPhoto, ENERGY_CLASS


class Cities(JsonPage):
    @method
    class get_city(DictElement):

        class item(ItemElement):
            klass = City

            obj_id = Dict('zoneIds/0')
            obj_name = CleanText(Dict('name'))


class MyItemElement(ItemElement):
    klass = Housing

    def condition(self):
        return not Dict('userRelativeData/isAdModifier')(self)

    obj_id = Dict('id')
    obj_title = Dict('title')
    obj_area = Dict('surfaceArea')
    obj_cost = Dict('price')

    def obj_price_per_meter(self):
        try:
            return Dict('pricePerSquareMeter')(self)
        except ItemNotFound:
            return NotAvailable

    obj_currency = 'EUR'
    obj_date = Date(Dict('publicationDate'))
    obj_location = CleanDecimal(Dict('postalCode'))
    obj_text = Dict('description', '')

    def obj_photos(self):
        return [HousingPhoto(photo['url']) for photo in Dict('photos')(self)]

    obj_rooms = Dict('roomsQuantity', 0)
    obj_bedrooms = Dict('bedroomsQuantity', 0)

    def obj_DPE(self):
        try:
            return ENERGY_CLASS[Dict('energyClassification')(self)]
        except (KeyError, ItemNotFound):
            return NotAvailable

    def obj_GES(self):
        try:
            return ENERGY_CLASS[Dict('greenhouseGazClassification')(self)]
        except (KeyError, ItemNotFound):
            return NotAvailable


class ResultsPage(JsonPage):
    @method
    class get_housings(DictElement):
        item_xpath = 'realEstateAds'

        class item(MyItemElement):
            pass


class HousingPage(JsonPage):
    @method
    class get_housing(MyItemElement):
        pass
