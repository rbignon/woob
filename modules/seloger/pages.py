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
from decimal import Decimal

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

from .constants import RET, TYPES, BASE_URL


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
                    Dict('cardType')(self) not in ['advertising', 'ali', 'localExpert']
                    and Dict('id', default=False)(self)
                    and Dict('classifiedURL', default='')(self).startswith(BASE_URL)
                )

            obj_id = Dict('id')

            def obj_type(self):
                idType = int(Env('query_type')(self))
                try:
                    type = next(k for k, v in TYPES.items() if v == idType)
                    if type == POSTS_TYPES.FURNISHED_RENT:
                        # SeLoger does not let us discriminate between furnished and not furnished.
                        return POSTS_TYPES.RENT
                    return type
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
        json_content = Regexp(
            CleanText('//script'),
            r"window\[\"initialData\"\] = JSON.parse\(\"({.*})\"\);"
        )(self.doc)
        json_content = codecs.unicode_escape_decode(json_content)[0]
        json_content = json_content.encode('utf-8', 'surrogatepass').decode('utf-8')
        self.doc = {
            "advert": json.loads(json_content).get('advert', {}).get('mainAdvert', {}),
            "agency": json.loads(json_content).get('agency', {})
        }

    @method
    class get_housing(ItemElement):
        klass = Housing

        def parse(self, el):
            self.agency_doc = el['agency']
            self.el = el['advert']

        obj_id = Dict('id')

        def obj_house_type(self):
            naturebien = CleanText(Dict('idEstateType'))(self)
            try:
                return next(k for k, v in RET.items() if v == naturebien)
            except StopIteration:
                return NotLoaded

        def obj_type(self):
            idType = Dict('idTransactionType')(self)
            type = next(k for k, v in TYPES.items() if v == idType)
            if type == POSTS_TYPES.FURNISHED_RENT:
                # SeLoger does not let us discriminate between furnished and not furnished.
                return POSTS_TYPES.RENT
            return type

        def obj_advert_type(self):
            if 'Agences' in self.agency_doc['type']:
                return ADVERT_TYPES.PROFESSIONAL
            else:
                return ADVERT_TYPES.PERSONAL

        def obj_photos(self):
            photos = []

            for photo in Dict('photoList')(self):
                photos.append(HousingPhoto(photo['fullscreenUrl']))

            return photos

        obj_title = Dict('title')

        def obj_location(self):
            address = Dict('address')(self)
            return u'%s %s (%s)' % (address['neighbourhood'] or "",
                                    address['city'],
                                    address['zipCode'])

        def obj_address(self):
            address = Dict('address')(self)

            p = PostalAddress()
            p.street = address['street'] or ""
            p.postal_code = address['zipCode']
            p.city = address['city']
            p.full_address = Field('location')(self)

            return p

        obj_text = Dict('description')

        def obj_cost(self):
            propertyPrice = Dict('propertyPrice')(self)
            return Decimal(propertyPrice['prix'])

        def obj_currency(self):
            propertyPrice = Dict('propertyPrice')(self)
            return propertyPrice['priceUnit']

        obj_price_per_meter = PricePerMeterFilter()

        obj_area = CleanDecimal(Dict('surface'))

        def obj_url(self):
            return self.page.url

        def obj_phone(self):
            return self.agency_doc.get('agencyPhoneNumber', {}).get('value',
                                                                    NotAvailable)

        def obj_utilities(self):
            mention = Dict('propertyPrice/priceSuffix', default="")(self)
            if mention and "CC" in mention:
                return UTILITIES.INCLUDED
            else:
                return UTILITIES.UNKNOWN

        obj_bedrooms = CleanDecimal(Dict('bedroomCount'), default=Decimal(0))
        obj_rooms = CleanDecimal(Dict('numberOfRooms'))


class HousingJsonPage(JsonPage):
    @method
    class get_housing(ItemElement):
        klass = Housing

        def obj_DPE(self):
            DPE = Dict("energie", default="")(self)
            if DPE['status'] > 0:
                return NotAvailable
            else:
                return getattr(ENERGY_CLASS, DPE['lettre'], NotAvailable)

        def obj_GES(self):
            GES = Dict("ges", default="")(self)
            if GES['status'] > 0:
                return NotAvailable
            else:
                return getattr(ENERGY_CLASS, GES['lettre'], NotAvailable)

        def obj_details(self):
            details = {}

            for c in Dict('categories')(self):
                if c['criteria']:
                    details[c['name']] = ' / '.join([_['value'] for _ in c['criteria']])

            for _, c in Dict('infos_acquereur')(self).items():
                for key, value in c.items():
                    details[key] = value

            return details
