# -*- coding: utf-8 -*-

# Copyright(C) 2013 Julien Veyssier
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


from datetime import date, datetime, time

from dateutil.parser import parse as parse_date

from woob.browser.elements import DictElement, ItemElement, ListElement, method
from woob.browser.filters.json import Dict, NotFound
from woob.browser.filters.standard import BrowserURL, CleanDecimal, CleanText, Env, Eval, Regexp
from woob.browser.pages import HTMLPage, JsonPage, pagination
from woob.capabilities.base import NotAvailable
from woob.capabilities.image import BaseImage, Thumbnail
from woob.capabilities.recipe import Comment, Recipe
from woob.tools.json import json


class Time(Dict):
    def filter(self, el):
        if el and not isinstance(el, NotFound):
            el = el.replace('PT', '')
            if el == u'P':
                return NotAvailable
            _time = parse_date(el, dayfirst=False, fuzzy=False)
            _time = _time - datetime.combine(date.today(), time(0))
            return _time.seconds // 60


class ResultsPage(HTMLPage):
    """ Page which contains results as a list of recipies
    """
    @pagination
    @method
    class iter_recipes(ListElement):
        item_xpath = '//article/div'

        def next_page(self):
            suivant = CleanText(
                '//li[@class="pagination-item"]/span/span[@class="pagination-txt" and text()="Suivant"]',
                default="")(self)
            if suivant == "Suivant":
                page = Env('page')(self)
                return BrowserURL('search', pattern=Env('pattern'), page=int(page) + 1)(self)

        class item(ItemElement):
            klass = Recipe

            obj_id = Regexp(CleanText('./div[@class="card-content"]/strong/a/@href'),
                            'https://www.750g.com/(.*).htm')

            obj_title = CleanText('./div[@class="card-content"]/strong/a')

            obj_short_description = CleanText('./div[@class="card-content"]/p[@class="card-text"]')

            class obj_picture(ItemElement):
                klass = BaseImage

                obj_thumbnail = Eval(Thumbnail,
                                     CleanText('./div[@class="card-media-wrapper"]/div/picture/@data-srcset'))


class CommentPage(JsonPage):
    """ Page which contains a comments
    """
    @method
    class get_comments(DictElement):
        item_xpath = "comments"

        class item(ItemElement):
            klass = Comment

            obj_id = Dict('@id')
            obj_author = Dict('author/nickname')
            obj_text = Dict('content')


class RecipePage(HTMLPage):
    """ Page which contains a recipe
    """

    @method
    class get_recipe(ItemElement):
        klass = Recipe

        def parse(self, el):
            json_content = CleanText('(//script[@type="application/ld+json"])[1]')(el)
            self.el = json.loads(json_content)

        obj_id = Env('id')
        obj_title = Dict('name')
        obj_ingredients = Dict('recipeIngredient')
        obj_cooking_time = Time('cookTime')
        obj_preparation_time = Time('prepTime')

        def obj_nb_person(self):
            return [CleanDecimal(Dict('recipeYield', default=0))(self)]

        obj_instructions = Dict('recipeInstructions')
        obj_author = Dict('author/name', default=NotAvailable)

        def obj_picture(self):
            img = BaseImage()
            img.url = self.el['image']['url']
            return img
