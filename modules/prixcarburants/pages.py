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

from woob.browser.elements import ItemElement, ListElement, method
from woob.browser.filters.standard import CleanDecimal, CleanText, Date, Env, Field, Format, Join
from woob.browser.pages import HTMLPage
from woob.capabilities.pricecomparison import Price, Product, Shop


class IndexPage(HTMLPage):

    def get_token(self):
        return CleanText('//input[@id="rechercher__token"]/@value')(self.doc)

    @method
    class iter_products(ListElement):
        item_xpath = '//div[@id="choix_carbu"]/fieldset/ul/li'

        class item(ItemElement):
            klass = Product

            obj_id = CleanText('./input/@value')
            obj_name = CleanText('./label')


class ComparisonResultsPage(HTMLPage):

    @method
    class iter_results(ListElement):
        item_xpath = '//table[@id="tab_resultat"]/tr'

        class item(ItemElement):
            klass = Price

            def condition(self):
                return CleanText('./@id', default=False)(self)

            obj_product = Env('product')

            def obj_id(self):
                product = Field('product')(self)
                _id = CleanText('./@id')(self)
                return u"%s.%s" % (product.id, _id)

            def obj_shop(self):
                _id = Field('id')(self)
                shop = Shop(_id)
                shop.name = CleanText('./td/div/div/span[@class="title"]')(self)
                shop.location = Format("%s %s",
                                       CleanText('(./td/div/div/span)[2]'),
                                       CleanText('(./td/div/div/span)[3]'))(self)
                return shop

            obj_date = Date(CleanText('(./td)[2]/span[2]'), dayfirst=True)
            obj_currency = u'EUR'
            obj_cost = CleanDecimal('(./td)[2]/span[1]')

    def get_product_name(self, product_id):
        return CleanText(
            f'//div[@id="affinage-choix_carbu"]/ul/li/input[@value="{product_id}"]/following-sibling::label',
            default='')(self.doc)


class ShopInfoPage(HTMLPage):
    def get_info(self):
        return Format("""
                        %s: %s<br/>
                        %s%s<br/>
                        %s:%s
                      """,
                      CleanText('//div[@class="infos"]/div[@id="infos-details"]/p[1]/strong'),
                      CleanText('//div[@class="infos"]/div[@id="infos-details"]/p[1]',
                                children=False),
                      CleanText('//div[@class="infos"]/div[@id="infos-details"]/p[2]/strong'),
                      CleanText('//div[@class="infos"]/div[@id="infos-details"]/p[2]',
                                children=False),
                      CleanText('//div[@class="infos"]/div/div[@class="services"]/strong'),
                      Join(addBefore='<ul><li>',
                           pattern='</li><li>',
                           addAfter='</li></ul>',
                           selector='//div[@class="infos"]/div/div[@class="services"]/div/img/@alt'))(self.doc)
