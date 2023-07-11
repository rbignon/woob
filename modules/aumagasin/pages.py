# Copyright(C) 2023      Bezleputh
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
import re

from woob.browser.elements import method, ListElement, ItemElement
from woob.browser.filters.standard import CleanText, Field
from woob.browser.pages import HTMLPage, pagination
from woob.capabilities import BaseObject
from woob.capabilities.address import PostalAddress
from woob.capabilities.contact import Place


class EnseignesListPage(HTMLPage):
    @method
    class list_enseignes(ListElement):
        item_xpath = r'//div[@class="list-item"]/div/a'

        class item(ItemElement):
            klass = BaseObject

            obj_id = CleanText('./h2')
            obj_url = CleanText('./@href')


class MagasinPage(HTMLPage):

    @pagination
    @method
    class iter_contacts(ListElement):
        item_xpath = '//div[@class="shop"]'

        def next_page(self):
            next_page = CleanText('//div[has-class("paginationBlock")][1]/ul/li[@class="reverse right "]/a/@href')(self)
            if next_page:
                return next_page

        class item(ItemElement):
            klass = Place

            obj_id = CleanText('./@data-id')
            obj_name = CleanText('./div/div/a/h2')
            obj_address = CleanText('./div/div/div[@class="font-weight-light"]')
            obj_url = CleanText('./div/div/a/@href')

            def obj_postal_address(self):
                address = Field('address')(self)
                p = PostalAddress()

                m = re.search(
                    r"(?P<street>[\w\s\-]*) - (?P<postal_code>(?:0[1-9]|[1-8]\d|9[0-8])\d{3}) (?P<city>[\w\s\-]*)",
                    address)

                if m:
                    p.street = m.group('street')
                    p.postal_code = m.group('postal_code')
                    p.city = m.group('city')

                p.full_address = address

                return p
