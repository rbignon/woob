# -*- coding: utf-8 -*-

# Copyright(C) 2019      Guntra
#
# This file is part of a weboob module.
#
# This weboob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This weboob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this weboob module. If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals
from weboob.browser.filters.standard import (
    CleanDecimal, CleanText,
    Date, Format, Lower, Regexp, QueryValue
)
from weboob.browser.filters.json import Dict
from weboob.browser.filters.html import Attr, AbsoluteLink
from weboob.browser.elements import ItemElement, ListElement, DictElement, method
from weboob.browser.pages import JsonPage, HTMLPage, pagination
from weboob.capabilities.base import Currency
from weboob.capabilities.housing import (
    Housing, HousingPhoto, City,
    POSTS_TYPES, HOUSE_TYPES, ADVERT_TYPES, UTILITIES
)


class CitiesPage(JsonPage):

    ENCODING = 'UTF-8'

    def build_doc(self, content):
        content = super(CitiesPage, self).build_doc(content)
        if content:
            return content
        else:
            return [{"locations": []}]

    @method
    class get_cities(DictElement):

        item_xpath = 'cities'

        class item(ItemElement):

            klass = City

            obj_id = Dict('id') & CleanText() & Lower()

            obj_name= Dict('value') & CleanText()


class SearchPage(HTMLPage):

    @pagination
    @method
    class iter_housings(ListElement):

        item_xpath = '//article[has-class("itemListe")]'

        next_page = AbsoluteLink('./div[@class="pagination-foot-bloc"]/a[@class="pageActive"][2]')

        class item(ItemElement):

            klass = Housing

            obj_id = QueryValue(
                Attr(
                    './/div[has-class("presentationItem")]/h2/a',
                    'href'
                ),
                'idter'
            )

            obj_url = AbsoluteLink('.//h2/a')

            obj_type = POSTS_TYPES.SALE

            obj_advert_type = ADVERT_TYPES.PROFESSIONAL

            obj_house_type = HOUSE_TYPES.LAND

            obj_title = CleanText('.//div[@class="presentationItem"]/h2/a')

            def obj_area(self):
                min_area = CleanDecimal(
                    Regexp(
                        CleanText('.//div[@class="presentationItem"]/h3'),
                        'surface de (\d+) m²'
                    )
                )(self)
                max_area = CleanDecimal(
                    Regexp(
                        CleanText('.//div[@class="presentationItem"]/h3'),
                        'à (\d+) m²',
                        default=0
                    )
                )(self)
                if (max_area > min_area):
                    return max_area
                else:
                    return min_area

            obj_cost = CleanDecimal(
                CleanText(
                    './/div[@class="presentationItem"]/h3/span[1]',
                    replace=[(".", ""),(" €","")]
                )
            )

            obj_currency = Currency.get_currency(u'€')

            obj_date = Date(
               CleanText(
                   './/div[@class="presentationItem"]//span[@class="majItem"]',
                   replace=[("Mise à jour : ", "")])
            )

            obj_location = CleanText('.//div[@class="presentationItem"]/h2/a/span')

            obj_text = CleanText('.//div[@class="presentationItem"]/p')

            obj_phone = CleanText('.//div[@class="divBoutonContact"]/div[@class="phone-numbers-bloc"]/p[1]/strong')

            def _photos_generator(self):
                for photo in self.xpath('.//div[has-class("photoItemListe")]/img/@data-src'):
                    yield HousingPhoto(self.page.absurl(photo))

            def obj_photos(self):
                return list(self._photos_generator())

            obj_utilities = UTILITIES.UNKNOWN

class HousingPage(HTMLPage):

    @method
    class get_housing(ItemElement):
        
        klass = Housing

        obj_id = Attr(
            '//article//a[has-class("add-to-selection")]',
            'data-id'
        )

        def obj_url(self):
            return self.page.url

        obj_type = POSTS_TYPES.SALE

        obj_advert_type = ADVERT_TYPES.PROFESSIONAL

        obj_house_type = HOUSE_TYPES.LAND

        obj_title = CleanText('//article[@id="annonceTerrain"]/header/h1')

        def obj_area(self):
            max_area = 0
            for land in self.xpath('//table[@id="price-list"]/tbody/tr'):
                area = CleanDecimal(
                    CleanText(
                        './td[2]',
                        replace=[("m²","")]
                    )
                )(land)
                if area > max_area:
                    max_area = area
            return max_area

        def obj_cost(self):
            min_cost = 0
            for land in self.xpath('//table[@id="price-list"]/tbody/tr'):
                cost = CleanDecimal(
                    CleanText(
                        './td[3]',
                        replace=[(".","")]
                    )
                )(land)
                if min_cost == 0:
                    min_cost = cost
                if cost < min_cost:
                    min_cost = cost
            return min_cost

        obj_currency = Currency.get_currency(u'€')

        obj_date = Date(
            CleanText('//section[@id="photos-details"]/div[@class="right-bloc"]/div/div[3]/div[2]/strong')
        )

        obj_location = CleanText('//article[@id="annonceTerrain"]/header/h1/strong')

        obj_text = CleanText('//div[@id="informationsTerrain"]/p[2]')

        obj_phone = CleanText('//div[@id="infos-annonceur"]/div/div/div[@class="phone-numbers-bloc"]/p/strong')

        def obj_photos(self):
            photos = []
            for photo in self.xpath('.//div[@id="miniatures-carousel"]/div'):
                photos.append(HousingPhoto(self.page.absurl(Attr('./img', 'data-big-photo')(photo))))
            return photos

        obj_utilities = UTILITIES.UNKNOWN
