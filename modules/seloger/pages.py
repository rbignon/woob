# -*- coding: utf-8 -*-

# Copyright(C) 2012 Romain Bignon
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


import codecs

from woob.browser.elements import DictElement, ItemElement, method
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import BrowserURL, CleanDecimal, CleanText, Currency, Env, Field, Regexp
from woob.browser.pages import HTMLPage, JsonPage, pagination
from woob.capabilities.address import PostalAddress
from woob.capabilities.base import NotAvailable, NotLoaded
from woob.capabilities.housing import ADVERT_TYPES, ENERGY_CLASS, POSTS_TYPES, UTILITIES, City, Housing, HousingPhoto
from woob.exceptions import ActionNeeded
from woob.tools.capabilities.housing.housing import PricePerMeterFilter
from woob.tools.json import json

from .constants import BASE_URL, RET, TYPES


class ErrorPage(HTMLPage):
    def on_load(self):
        raise ActionNeeded("Please resolve the captcha")


class CitiesPage(JsonPage):
    @method
    class iter_cities(DictElement):
        ignore_duplicate = True

        class item(ItemElement):
            klass = City

            obj_id = Dict('Params/ci')
            obj_name = Dict('Display')


class SearchResultsPage(HTMLPage):
    def __init__(self, *args, **kwargs):
        HTMLPage.__init__(self, *args, **kwargs)
        json_content = Regexp(CleanText('//script'),
                              r"window\[\"initialData\"\] = JSON.parse\(\"({.*})\"\);window\[\"tags\"\]")(self.doc)
        json_content = codecs.unicode_escape_decode(json_content)[0]
        json_content = json_content.encode('utf-8', 'surrogatepass').decode('utf-8')
        self.doc = json.loads(json_content)

    @pagination
    @method
    class iter_housings(DictElement):
        ignore_duplicate = True

        item_xpath = 'cards/list'

        def next_page(self):
            page_nb = Dict('navigation/pagination/page')(self)
            max_results = Dict('navigation/counts/count')(self)
            results_per_page = Dict('navigation/pagination/resultsPerPage')(self)

            if int(max_results) / int(results_per_page) > int(page_nb):
                return BrowserURL('search', query=Env('query'), page_number=int(page_nb) + 1)(self)

        class item(ItemElement):
            klass = Housing

            def condition(self):
                return (
                    Dict('classifiedURL', default=False)(self)
                    and Dict('id', default=False)(self)
                    and (
                        Dict('classifiedURL', default='')(self).startswith(BASE_URL) or
                        int(Env('query_type')(self)) == TYPES[POSTS_TYPES.RENT]
                    )
                )

            obj_id = Dict('id')

            def obj_type(self):
                id_type = int(Env('query_type')(self))
                try:
                    post_type = next(k for k, v in TYPES.items() if v == id_type)
                    if post_type == POSTS_TYPES.FURNISHED_RENT:
                        # SeLoger does not let us discriminate between furnished and not furnished.
                        return POSTS_TYPES.RENT
                    return post_type
                except StopIteration:
                    return NotAvailable

            def obj_house_type(self):
                naturebien = CleanText(Dict('estateTypeId'))(self)
                try:
                    return next(k for k, v in RET.items() if v == naturebien)
                except StopIteration:
                    return NotLoaded

            def obj_title(self):
                return "{} - {} - {}".format(Dict('estateType')(self),
                                             " / ".join(Dict('tags')(self)),
                                             Field('location')(self))

            def obj_advert_type(self):
                is_agency = Dict('contact/agencyId', default=False)(self)
                if is_agency:
                    return ADVERT_TYPES.PROFESSIONAL
                else:
                    return ADVERT_TYPES.PERSONAL

            obj_utilities = UTILITIES.UNKNOWN

            def obj_photos(self):
                photos = []
                for photo in Dict('photos')(self):
                    photos.append(HousingPhoto(photo))
                return photos

            def obj_location(self):
                quartier = Dict('districtLabel')(self)
                quartier = quartier if quartier else ''
                ville = Dict('cityLabel')(self)
                ville = ville if ville else ''
                cp = Dict('zipCode')(self)
                cp = f'({cp})' if cp else ''
                return u'%s %s %s' % (quartier, ville, cp)

            obj_url = Dict('classifiedURL')

            obj_text = Dict('description')

            obj_cost = CleanDecimal(Dict('pricing/price', default=''), default=NotLoaded)
            obj_currency = Currency(Dict('pricing/price', default=''), default=NotLoaded)
            obj_area = CleanDecimal(Dict('surface'))

            def obj_price_per_meter(self):
                ppm = CleanDecimal(Dict('pricing/squareMeterPrice'), default='')(self)
                if not ppm:
                    ppm = PricePerMeterFilter()(self)
                return ppm


class HousingPage(HTMLPage):

    def __init__(self, *args, **kwargs):
        HTMLPage.__init__(self, *args, **kwargs)
        self.doc = json.loads(CleanText('//script[@id="__NEXT_DATA__"]')(self.doc))

    @method
    class get_housing(ItemElement):
        klass = Housing

        obj_id = Dict('props/pageProps/listingData/listing/listingDetail/id')

        def obj_house_type(self):
            naturebien = CleanText(Dict('props/pageProps/listingData/listing/listingDetail/propertyTypeId'))(self)
            try:
                return next(k for k, v in RET.items() if v == naturebien)
            except StopIteration:
                return NotLoaded

        def obj_type(self):
            id_type = Dict('props/pageProps/listingData/listing/listingDetail/transactionTypeId')(self)
            post_type = next(k for k, v in TYPES.items() if v == id_type)
            if post_type == POSTS_TYPES.FURNISHED_RENT:
                # SeLoger does not let us discriminate between furnished and not furnished.
                return POSTS_TYPES.RENT
            return post_type

        def obj_advert_type(self):
            if Dict('props/pageProps/listingData/agency/id', default=None)(self) is not None:
                return ADVERT_TYPES.PROFESSIONAL
            else:
                return ADVERT_TYPES.PERSONAL

        def obj_photos(self):
            photos = []

            for photo in Dict('props/pageProps/listingData/listing/listingDetail/media/photos')(self):
                photos.append(HousingPhoto(photo['defaultUrl']))

            return photos

        obj_title = Dict('props/pageProps/listingData/listing/listingDetail/title')

        def obj_location(self):
            address = Dict('props/pageProps/listingData/listing/listingDetail/address')(self)
            return f'{address["district"] or ""} {address["city"]} ({address["postalCode"]})'.strip()

        def obj_address(self):
            address = Dict('props/pageProps/listingData/listing/listingDetail/address')(self)

            p = PostalAddress()
            p.street = address['street'] or ""
            p.postal_code = address['postalCode']
            p.city = address['city']
            p.full_address = Field('location')(self)

            return p

        obj_text = Dict('props/pageProps/listingData/listing/listingDetail/descriptive')

        obj_cost = Dict('props/pageProps/listingData/listing/listingDetail/listingPrice/price')

        obj_currency = Dict('props/pageProps/listingData/listing/listingDetail/listingPrice/priceUnit')
        obj_price_per_meter = PricePerMeterFilter()

        obj_area = Dict('props/pageProps/listingData/listing/listingDetail/surface')

        obj_url = Dict('props/pageProps/listingData/listing/url/value')

        def obj_phone(self):
            if Dict('props/pageProps/listingData/agency/id', default=None)(self) is not None:
                return Dict('props/pageProps/listingData/agency/phoneNumber')
            return NotAvailable

        def obj_utilities(self):
            mention = \
                Dict(
                    'props/pageProps/listingData/listing/listingDetail/listingPrice/price/priceInformation',
                    default="")(self)
            if mention and "cc" in mention:
                return UTILITIES.INCLUDED
            else:
                return UTILITIES.UNKNOWN

        obj_bedrooms = CleanDecimal(Dict('props/pageProps/listingData/listing/listingDetail/bedroomCount'),
                                    default=NotAvailable)
        obj_rooms = CleanDecimal(Dict('props/pageProps/listingData/listing/listingDetail/roomCount'),
                                 default=NotAvailable)

        def obj_DPE(self):
            dpe = \
                Dict(
                    "props/pageProps/listingData/listing/listingDetail/energyPerformanceCertificate/electricityRating",
                    default=None)(self)
            if dpe is not None:
                return getattr(ENERGY_CLASS, dpe, NotAvailable)
            return NotAvailable

        def obj_GES(self):
            ges = Dict("props/pageProps/listingData/listing/listingDetail/energyPerformanceCertificate/gasRating",
                       default=None)(self)
            if ges is not None:
                return getattr(ENERGY_CLASS, ges, NotAvailable)
            return NotAvailable

        def obj_details(self):
            details = {}
            for k, v in Dict('props/pageProps/listingData/listing/listingDetail/featureCategories')(self).items():
                if type(v) == dict and 'features' in v.keys():
                    for _ in v['features']:
                        details[_['name']] = _['title']
            return details
