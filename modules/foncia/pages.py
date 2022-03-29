# -*- coding: utf-8 -*-

# Copyright(C) 2017      Phyks (Lucas Verney)
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

from __future__ import unicode_literals
from decimal import Decimal
import requests
from woob.browser.elements import ItemElement, method, DictElement
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import (
    Format, DateTime, CleanDecimal, Field)
from woob.browser.pages import JsonPage, pagination
from woob.browser.selenium import SeleniumPage
from woob.capabilities.address import PostalAddress
from woob.capabilities.base import NotAvailable, NotLoaded
from woob.capabilities.housing import (
    City, Housing, HousingPhoto, POSTS_TYPES,
    ENERGY_CLASS, ADVERT_TYPES, UTILITIES
)
from woob.tools.capabilities.housing.housing import PricePerMeterFilter
from .constants import QUERY_TYPES, QUERY_HOUSE_TYPES, BASE_URL, AVAILABLE_TYPES


class FonciaItemElement(ItemElement):
    klass = Housing

    obj_id = Format('%s/%s', Dict('typeAnnonce'), Dict('reference'))
    obj_url = Format(f'{BASE_URL}%s', Dict('canonicalUrl'))
    obj_advert_type = ADVERT_TYPES.PROFESSIONAL

    def obj_area(self):
        area = Dict('surface/totale', default=None)(self)
        if area is None:
            area = Dict('surface/habitable', default=None)(self)

        return Decimal(area)

    def obj_cost(self):
        if Field('type')(self) == POSTS_TYPES.SALE:
            return CleanDecimal(Dict('prixVente', default=0))(self)
        else:
            return CleanDecimal(Dict('loyer'))(self) +\
                   CleanDecimal(Dict('loyerAnnexe', default=0))(self)

    obj_currency = '€'
    obj_price_per_meter = PricePerMeterFilter()

    def obj_text(self):
        text = Dict('description', default=None)(self)
        if text is None:
            text = Dict('libelle')(self)
        return text

    obj_date = DateTime(Dict('datePublication'))
    obj_rooms = CleanDecimal(Dict('nbPiece', default=NotAvailable), default=NotAvailable)
    obj_bedrooms = CleanDecimal(Dict('nbChambre', default=NotAvailable), default=NotAvailable)
    obj_title = Format(r'%s %s - %sm²',
                       Dict('typeBien'),
                       Dict('localisation/locality/libelleDisplay'),
                       Format('%.2f', Field('area')))

    def obj_address(self):
        location = PostalAddress()
        location.postal_code = Dict('localisation/codePostal')(self)
        location.city = Dict('localisation/ville')(self)
        location.full_address = f'{location.city} ({location.postal_code})'
        return location

    def obj_type(self):
        _ = Dict('typeAnnonce')(self)
        for k, v in QUERY_TYPES.items():
            if v == _:

                if k == POSTS_TYPES.RENT and Dict('typeBien') in AVAILABLE_TYPES[POSTS_TYPES.FURNISHED_RENT]:
                    return POSTS_TYPES.FURNISHED_RENT
                return k
        return NotAvailable

    def obj_house_type(self):
        _ = Dict('typeBien')(self)
        for house_type, types in QUERY_HOUSE_TYPES.items():
            if _ in types:
                return house_type
        return NotLoaded

    def obj_photos(self):
        return [HousingPhoto(url) for url in Dict('medias', default=[])(self)]

    def obj_DPE(self):
        return getattr(ENERGY_CLASS, Dict('noteConsoEnergie', default='')(self), NotAvailable)

    def obj_GES(self):
        return getattr(ENERGY_CLASS, Dict('noteEmissionGES', default='')(self), NotAvailable)

    def obj_utilities(self):
        if Field('type')(self) == POSTS_TYPES.SALE:
            return UTILITIES.UNKNOWN
        return UTILITIES.INCLUDED


class IndexPage(SeleniumPage):
    pass


class CitiesPage(JsonPage):
    @method
    class iter_cities(DictElement):
        item_xpath = 'localities'
        ignore_duplicate = True

        class item(ItemElement):
            klass = City

            obj_id = Dict('slug')
            obj_name = Dict('libelleDisplay')


class HousingPage(JsonPage):

    def get_agency_id(self):
        return Dict('numeroAgence')(self.doc)

    @method
    class get_housing(FonciaItemElement):
        def obj_details(self):
            details = {}

            for k, v in Dict('caracteristiques', default={})(self).items():
                if type(v) is dict:
                    if v.get('available', False):
                        details[k] = ''
                else:
                    details[k] = v

            copro = Dict('copro', default=False)(self)
            if copro:
                details = {**details, **copro}

            return details


class SearchResultsPage(JsonPage):
    @pagination
    @method
    class iter_housings(DictElement):
        item_xpath = 'annonces'

        def next_page(self):
            if Dict('count')(self) > 0:
                data = self.env['data']
                data['page'] = data['page'] + 1
                return requests.Request('POST', self.page.url, json=data)

        class item(FonciaItemElement):
            pass


class AgencyPage(JsonPage):
    def get_phone(self):
        return Dict('tel')(self.doc)
