# -*- coding: utf-8 -*-

# Copyright(C) 2017      Antoine BOSSY
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

from woob.browser.elements import DictElement, ItemElement, ListElement, method
from woob.browser.filters.html import AbsoluteLink, Attr, Link, XPath
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import CleanDecimal, CleanText, Env, MultiJoin, Regexp
from woob.browser.pages import HTMLPage, JsonPage, pagination
from woob.capabilities.address import PostalAddress
from woob.capabilities.base import Currency, NotAvailable
from woob.capabilities.housing import (
    ADVERT_TYPES, ENERGY_CLASS, HOUSE_TYPES, POSTS_TYPES, UTILITIES, City, Housing, HousingPhoto,
)
from woob.tools.capabilities.housing.housing import PricePerMeterFilter

from .constants import HOUSE_TYPES_LABELS


class SearchCityPage(JsonPage):

    @method
    class iter_cities(DictElement):

        class item(ItemElement):
            klass = City
            obj_id = MultiJoin(Dict('id', default=''),
                               Dict('type', default=''),
                               Dict('insee', default=''),
                               pattern='#')
            obj_name = Dict('label', default='')


class SearchPage(HTMLPage):
    @pagination
    @method
    class iter_housings(ListElement):
        item_xpath = '//li[has-class("item")]/div[@class="itemInfo"]'

        next_page = AbsoluteLink('//span[has-class("selected")]//following-sibling::span/a')

        class item(ItemElement):
            klass = Housing
            obj_id = Attr('./div[@class="itemImage"]/a', 'data-id')
            obj_url = AbsoluteLink('./div[@class="itemImage"]/a')
            obj_cost = CleanDecimal('./div[@class="itemContent"]/div/h4', default=NotAvailable)
            obj_currency = Currency.get_currency(u'€')
            obj_area = CleanDecimal(Regexp(CleanText('./div[@class="itemImage"]/a/@data-title'),
                                           r' (\d+)m²',
                                           default=NotAvailable),
                                    default=NotAvailable)
            obj_title = CleanText('./h3/a')
            obj_text = MultiJoin(CleanText('./div[@class="itemContent"]/div/p'),
                                 CleanText('./div[@class="itemContent"]/div/div[@class="nom"]'),
                                 CleanText('./div[@class="itemContent"]/div/div/div[@class="actions"]/span'),
                                 pattern=' / ')
            obj_rooms = CleanDecimal(Regexp(CleanText('./div[@class="itemImage"]/a/@data-title'), r' (\d+) pièces',
                                            default=NotAvailable),
                                     default=NotAvailable)
            obj_phone = CleanText('./div[@class="itemContent"]/div/div/div/span[@class="telNumber"]',
                                  default=NotAvailable)
            obj_utilities = UTILITIES.UNKNOWN
            obj_advert_type = ADVERT_TYPES.PROFESSIONAL

            def obj_house_type(self):
                _ = CleanText('./div/a[@class="ajoutFavoris"]/@data-type')(self)
                return HOUSE_TYPES_LABELS[_] if _ in HOUSE_TYPES_LABELS.keys() else HOUSE_TYPES.UNKNOWN

            def obj_type(self):
                url = self.obj_url(self)
                return POSTS_TYPES.SALE if 'acheter' in url else POSTS_TYPES.RENT

            def obj_photos(self):
                return [HousingPhoto(AbsoluteLink('./div[@class="itemImage"]/a/img', 'src')(self))]


class HousingPage(HTMLPage):
    @method
    class get_housing(ItemElement):
        klass = Housing

        obj_id = Env('id')
        obj_title = CleanText('//h1[@class="titreFiche"]')
        obj_cost = CleanDecimal('.//span[@itemprop="price"]', default=NotAvailable)
        obj_currency = Attr('//meta[@itemprop="priceCurrency"]', 'content', default=NotAvailable)
        obj_price_per_meter = PricePerMeterFilter()
        obj_area = CleanDecimal('.//li[has-class("surface")]//b', default=NotAvailable)
        obj_text = CleanText('.//p[@itemprop="description"]')
        obj_advert_type = ADVERT_TYPES.PROFESSIONAL
        obj_url = CleanText('//link[@rel="canonical"]/@href')
        obj_utilities = UTILITIES.UNKNOWN
        obj_rooms = CleanDecimal('//li[has-class("pieces")]//b', default=NotAvailable)

        def obj_phone(self):
            _ = CleanText('.//span[@id="agence_call"]', default=None)(self)
            if _:
                return _.split(' : ')[-1]

        def obj_photos(self):
            photos = []
            for photo in self.xpath('.//a[has-class("imageAnnonce")]'):
                photos.append(HousingPhoto(Link('.')(photo)))
            return photos

        def obj_type(self):
            url = self.obj_url(self)
            return POSTS_TYPES.SALE if 'acheter' in url else POSTS_TYPES.RENT

        def obj_details(self):
            details = {}
            for el in XPath('//ul[@class="infos"]/li')(self):
                _ = CleanText('.')(el).split(':')
                if _:
                    details[_[0]] = _[1]
            return details

        def obj_address(self):
            location = PostalAddress()
            location.postal_code = CleanText('(//meta[@itemprop="postalcode"])[1]/@content')(self)
            location.city = CleanText('(//meta[@itemprop="addresslocality"])[1]/@content')(self)
            location.street = CleanText('(//meta[@itemprop="streetAddress"])[1]/@content')(self)
            location.full_address = CleanText('(//div[@itemprop="address"])[1]')(self)
            return location

        def obj_house_type(self):
            _ = CleanText('//meta[@itemprop="model"]/@content')(self)
            return HOUSE_TYPES_LABELS[_] if _ in HOUSE_TYPES_LABELS.keys() else HOUSE_TYPES.UNKNOWN

        def obj_DPE(self):
            electric_consumption = CleanDecimal('//div[@data-id="dpeValue"]/div/div[@class="dpeValue"]',
                                                default=None)(self)

            if electric_consumption is not None:
                if electric_consumption <= 50:
                    return ENERGY_CLASS.A
                elif 50 < electric_consumption <= 90:
                    return ENERGY_CLASS.B
                elif 90 < electric_consumption <= 150:
                    return ENERGY_CLASS.C
                elif 150 < electric_consumption <= 230:
                    return ENERGY_CLASS.D
                elif 230 < electric_consumption <= 330:
                    return ENERGY_CLASS.E
                elif 330 < electric_consumption <= 450:
                    return ENERGY_CLASS.F
                else:
                    return ENERGY_CLASS.G
            return NotAvailable

        def obj_GES(self):
            gas_consumption = CleanDecimal('//div[@data-id="dpeValue"]/div/div[@class="gesValue"]',
                                           default=None)(self)

            if gas_consumption is not None:
                if gas_consumption <= 5:
                    return ENERGY_CLASS.A
                elif 5 < gas_consumption <= 10:
                    return ENERGY_CLASS.B
                elif 11 < gas_consumption <= 20:
                    return ENERGY_CLASS.C
                elif 21 < gas_consumption <= 35:
                    return ENERGY_CLASS.D
                elif 36 < gas_consumption <= 55:
                    return ENERGY_CLASS.E
                elif 56 < gas_consumption <= 80:
                    return ENERGY_CLASS.F
                else:
                    return ENERGY_CLASS.G
            return NotAvailable
