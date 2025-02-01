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

from woob.browser.elements import DictElement, ItemElement, ListElement, method
from woob.browser.filters.html import AbsoluteLink, Attr, XPath
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import CleanDecimal, CleanText, DateTime, Env, Format, Join, Regexp
from woob.browser.pages import HTMLPage, JsonPage, pagination
from woob.capabilities.base import Currency, NotAvailable
from woob.capabilities.housing import (
    ADVERT_TYPES,
    ENERGY_CLASS,
    HOUSE_TYPES,
    POSTS_TYPES,
    UTILITIES,
    City,
    Housing,
    HousingPhoto,
)
from woob.tools.capabilities.housing.housing import PricePerMeterFilter
from woob.tools.json import json

from .constants import FURNISHED_VALUES, QUERY_HOUSE_TYPES_LABELS, QUERY_TYPES, QUERY_TYPES_LABELS


class CitiesPage(JsonPage):

    @method
    class iter_cities(DictElement):

        class item(ItemElement):
            klass = City
            obj_id = Dict("Value")
            obj_name = Dict("Name")


class SearchPage(HTMLPage):
    @pagination
    @method
    class iter_housings(ListElement):
        item_xpath = ".//div[@data-tranid]"

        next_page = AbsoluteLink('./ul[@class="pager"]/li[@id="pager-next"]/a')

        class item(ItemElement):
            klass = Housing

            obj_url = AbsoluteLink('.//a[@class="listing-item-link"]')
            obj_location = CleanText('.//div[@class="listing-city"]')
            obj_phone = CleanText(Attr(".", "data-infos"))
            obj_advert_type = ADVERT_TYPES.PERSONAL
            obj_text = ""

            obj_id = Regexp(CleanText('.//a[@class="listing-item-link"]/@href', replace=[("/", "#")]), r"^#(.*)\.html")

            obj_title = Format(
                "%s %s %s",
                CleanText('.//div[@class="listing-type"]'),
                CleanText('.//div[@class="listing-city"]'),
                Join(" ", './/div[@class="listing-characteristics-item"]'),
            )

            obj_area = CleanDecimal(CleanText('.//div[@class="listing-characteristics"]/div[2]'), default=NotAvailable)

            obj_cost = CleanDecimal(CleanText('.//div[@class="listing-price-value"]'))
            obj_price_per_meter = PricePerMeterFilter()
            obj_currency = CleanText(Regexp(CleanText('.//div[@class="listing-price-value"]'), r"[\d\ ]+(.*)"))

            def obj_utilities(self):
                price = CleanText('//span[@class="listing-price--details"]')(self)
                if "CC" in price:
                    return UTILITIES.INCLUDED
                elif "HC" in price:
                    return UTILITIES.EXCLUDED
                else:
                    return UTILITIES.UNKNOWN

            def obj_photos(self):
                photos = []
                for photo in XPath('.//span[@class="listing-item-img"]/img')(self):
                    photos.append(HousingPhoto(CleanText("./@src")(photo)))
                return photos

            def obj_type(self):
                if Env("type_id")(self) == QUERY_TYPES[POSTS_TYPES.SALE]["searchTypeID"]:
                    return (
                        POSTS_TYPES.SALE
                        if Env("group_id")(self) == QUERY_TYPES[POSTS_TYPES.SALE]["typeGroupCategoryID"]
                        else POSTS_TYPES.VIAGER
                    )
                else:
                    return (
                        POSTS_TYPES.FURNISHED_RENT
                        if Env("furnished")(self) == FURNISHED_VALUES["YES"]
                        else POSTS_TYPES.RENT
                    )

            def obj_house_type(self):
                return QUERY_HOUSE_TYPES_LABELS.get(CleanText('.//div[@class="listing-type"]')(self), HOUSE_TYPES.OTHER)


class HousingPage(HTMLPage):
    ENCODING = "utf-8"

    def build_doc(self, content):
        content = HTMLPage.build_doc(self, content)
        return json.loads(Regexp(CleanText("//script"), r".*AppAdview, ({.*})\), document.*")(content))

    @method
    class get_housing(ItemElement):
        klass = Housing

        obj_id = CleanText(Env("id"), replace=[("/", "#")])

        def obj_url(self):
            return self.page.url

        obj_area = CleanDecimal(Dict("details/CacheHeaders/Value/Surface"), default=NotAvailable)
        obj_rooms = CleanDecimal(Dict("details/CacheHeaders/Value/RoomsCount"), default=NotAvailable)
        obj_bedrooms = CleanDecimal(Dict("details/CacheHeaders/Value/BedroomsCount"), default=NotAvailable)
        obj_cost = CleanDecimal(Dict("details/CacheHeaders/Value/Price"), default=NotAvailable)
        obj_currency = Currency.get_currency("€")
        obj_location = CleanText(Dict("details/CacheHeaders/Value/LocalityName"), default=NotAvailable)
        obj_title = CleanText(Dict("details/CacheHeaders/Value/Title"), default=NotAvailable)
        obj_text = CleanText(Dict("details/CacheHeaders/Value/Description"), default=NotAvailable)
        obj_date = DateTime(Dict("details/CacheHeaders/Value/ReleaseDate"))
        obj_advert_type = ADVERT_TYPES.PERSONAL
        obj_station = NotAvailable
        obj_price_per_meter = PricePerMeterFilter()
        obj_phone = Format("0%s", CleanText(Dict("details/CacheHeaders/Value/PhoneNumber"), default=NotAvailable))

        def obj_type(self):
            _ = QUERY_TYPES_LABELS.get(Dict("details/PropertyTransactionLabel")(self), NotAvailable)
            if _ == POSTS_TYPES.RENT:
                for _ in Dict("details/Description/OtherCharacteristics")(self):
                    if _["ID"] == "Conveniences" and _["Name"] == "Meublé":
                        return POSTS_TYPES.FURNISHED_RENT
            return _

        def obj_photos(self):
            photos = []
            for photo in Dict("details/CacheHeaders/Value/Photos")(self):
                photos.append(HousingPhoto(photo["Url"]))
            return photos

        def obj_DPE(self):
            return getattr(ENERGY_CLASS, Dict("details/CacheHeaders/Value/Diagnostic/EnergySymbol")(self), NotAvailable)

        def obj_GES(self):
            return getattr(ENERGY_CLASS, Dict("details/CacheHeaders/Value/Diagnostic/GasSymbol")(self), NotAvailable)

        def obj_utilities(self):
            if Dict("details/CacheHeaders/Value/IncludedBills")(self):
                return UTILITIES.INCLUDED
            return UTILITIES.EXCLUDED

        def obj_house_type(self):
            return QUERY_HOUSE_TYPES_LABELS.get(Dict("details/PropertyTypeLabel")(self), HOUSE_TYPES.OTHER)
