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

import datetime
import re

from woob.browser.elements import ItemElement, ListElement, method
from woob.browser.filters.html import XPath
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import CleanText, Env, Eval, Format, Join, Regexp, Time
from woob.browser.pages import HTMLPage, pagination
from woob.capabilities.image import BaseImage, Thumbnail
from woob.capabilities.recipe import Comment, Recipe
from woob.tools.json import json


class CuisineazDuration(Time):
    klass = datetime.timedelta
    _regexp = re.compile(r"PT((?P<hh>\d+)H)?((?P<mm>\d+)M)?")
    kwargs = {"hours": "hh", "minutes": "mm"}


class ResultsPage(HTMLPage):
    """Page which contains results as a list of recipies"""

    @pagination
    @method
    class iter_recipes(ListElement):
        item_xpath = "//article[@id]"

        def next_page(self):
            next = CleanText('//li[@class="pagination-next"]/span/a/@href', default=None)(self)
            if next:
                return next

        class item(ItemElement):
            klass = Recipe

            def condition(self):
                return Regexp(CleanText("./div/h2/a/@href"), "/recettes/(.*).aspx", default=None)(self.el)

            obj_id = Regexp(CleanText("./div/h2/a/@href"), "/recettes/(.*).aspx")
            obj_title = CleanText("./div/h2/a")

            class obj_picture(ItemElement):
                klass = BaseImage

                url = CleanText(
                    './div[has-class("searchImg")]/span/img[@data-src!=""]/@data-src|./div[has-class("searchImg")]/div/span/img[@src!=""]/@src',
                    default=None,
                )
                obj_thumbnail = Eval(Thumbnail, Format("http:%s", url))

                def validate(self, obj):
                    return obj.thumbnail.url != "http:"

            obj_short_description = CleanText('./div[has-class("show-for-medium")]')


class RecipePage(HTMLPage):
    """Page which contains a recipe"""

    @method
    class get_recipe(ItemElement):
        klass = Recipe

        def parse(self, el):
            items = XPath('//script[@type="application/ld+json"]')(self)
            for item in items:
                content = json.loads(CleanText(".")(item))
                for el in content:
                    if el["@type"] == "Recipe":
                        self.el = el
                        break

        obj_id = Env("id")
        obj_title = Dict("name")
        obj_ingredients = Dict("recipeIngredient")

        class obj_picture(ItemElement):
            klass = BaseImage

            def obj_url(self):
                url = Dict("image", default="")(self)
                return url[0] if url else url

            obj_thumbnail = Eval(Thumbnail, obj_url)

        obj_instructions = Join("\n\n - ", Dict("recipeInstructions"), addBefore=" - ")

        def obj_preparation_time(self):
            duration = CuisineazDuration(Dict("prepTime"))(self)
            return int(duration.total_seconds() / 60)

        def obj_cooking_time(self):
            duration = CuisineazDuration(Dict("cookTime"))(self)
            return int(duration.total_seconds() / 60)

        def obj_nb_person(self):
            return [Dict("recipeYield")(self)]

    @method
    class get_comments(ListElement):
        item_xpath = '//div[has-class("comment")]'

        class item(ItemElement):
            klass = Comment

            obj_author = CleanText('./div[@class="author"]')

            obj_text = CleanText("./p")

            def obj_rate(self):
                return len(XPath('./div/div/div[@class="icon-star"]')(self))
