# -*- coding: utf-8 -*-

# Copyright(C) 2017      Antoine BOSSY
#
# This file is part of weboob.
#
# weboob is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# weboob is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with weboob. If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals


from weboob.browser.pages import HTMLPage, JsonPage, pagination
from weboob.browser.elements import ItemElement, ListElement, method, DictElement
from weboob.browser.filters.html import Attr, AbsoluteLink, Link
from weboob.browser.filters.json import Dict

from weboob.browser.filters.standard import CleanDecimal, CleanText, Regexp
from weboob.capabilities.base import NotAvailable, Currency

from weboob.capabilities.housing import City, Housing, UTILITIES, HousingPhoto


class SearchCityPage(JsonPage):

    @method
    class iter_cities(DictElement):

        class item(ItemElement):
            klass = City
            obj_id = Dict('id')
            obj_name = Dict('label')


class SearchPage(HTMLPage):
    @pagination
    @method
    class iter_housings(ListElement):
        item_xpath = '//li[has-class("item")]'

        next_page = AbsoluteLink('//span[has-class("selected")]//following-sibling::span/a')

        class item(ItemElement):
            klass = Housing
            obj_id = Attr('.//footer//ul[has-class("infos")]//li[has-class("suivre")]//a[@data-type="ep-suivre"]', 'data-ep-id')
            obj_url = AbsoluteLink('.//h3[@id and contains(@id,"responsive-prix-mobile")]//a')
            obj_cost = CleanDecimal('.//div[has-class("js-block-responsive")]//h4', default=NotAvailable)
            obj_currency = Currency.get_currency(u'€')
            obj_area = CleanDecimal(Regexp(CleanText('.//ul[has-class("infos")]//li[has-class("surface")]//b'), r'([\d\ ]+)m', default=NotAvailable), default=NotAvailable)
            obj_title = CleanText('.//h3[contains(@id, "responsive-prix-mobile")]//a')
            obj_text = CleanText('.//p[has-class("resume")]')
            obj_rooms = CleanDecimal(Regexp(CleanText('.//ul[has-class("infos")]//li[has-class("rooms")]//b'), r'([\d\ ]+)m', default=NotAvailable), default=NotAvailable)
            obj_phone = CleanText('.//span[has-class("tel")]//span[contains(@id, "agence_call")]', default=NotAvailable)
            obj_utilities = UTILITIES.UNKNOWN

            def obj_photos(self):
                return [HousingPhoto(Attr('.//a[has-class("visuel")]//img', 'src')(self))]


class HousingPage(HTMLPage):
    @method
    class get_housing(ItemElement):
        klass = Housing

        obj_url = AbsoluteLink('.//a[has-class("actif")]')

        obj_id = Attr('//a[has-class("masquer")]', 'data-tpl-id')

        obj_cost = CleanDecimal('.//span[@itemprop="price"]', default=NotAvailable)
        obj_currency = Attr('//meta[@itemprop="priceCurrency"]', 'content', default=NotAvailable)

        def obj_utilities(self):
            if CleanText('.//span[has-class("alur")]')(self) == 'Charges comprises':
                return UTILITIES.INCLUDED
            elif CleanText('.//span[has-class("alur")]')(self) == 'Hors charges':
                return UTILITIES.EXCLUDED
            else:
                return UTILITIES.UNKNOWN
        obj_rooms = CleanDecimal('//li[has-class("pieces")]//b', default=NotAvailable)

        def obj_photos(self):
            photos = []
            for photo in self.xpath('.//a[has-class("imageAnnonce")]'):
                photos.append(HousingPhoto(Link('.')(photo)))
            return photos

        obj_area = CleanDecimal('.//li[has-class("surface")]//b', default=NotAvailable)
        obj_text = CleanText('.//p[@itemprop="description"]')
        obj_phone = CleanText('.//span[@id="agence_call"]')
