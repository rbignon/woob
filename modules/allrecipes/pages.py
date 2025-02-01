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
import re
from datetime import timedelta

from woob.browser.elements import DictElement, ItemElement, ListElement, method
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import BrowserURL, CleanText, Env, Eval, Join, Regexp, Time
from woob.browser.pages import HTMLPage, JsonPage, pagination
from woob.capabilities.base import NotAvailable
from woob.capabilities.image import BaseImage, Thumbnail
from woob.capabilities.recipe import Comment, Recipe
from woob.tools.json import json


class AllRecipesDuration(Time):
    klass = timedelta
    _regexp = re.compile(r"P0DT((?P<hh>\d+)H)?((?P<mm>\d+)M)?")
    kwargs = {"hours": "hh", "minutes": "mm"}


class ResultsPage(JsonPage):
    # actually, we parse the page as HTML, and lxml won't recognize utf-8-sig
    ENCODING = "utf-8"

    has_next = False

    def build_doc(self, content):
        content = JsonPage.build_doc(self, content)
        self.has_next = content["hasNext"]
        html_page = HTMLPage(self.browser, self.response)
        return html_page.build_doc(content["html"].encode(self.encoding))

    @pagination
    @method
    class iter_recipes(ListElement):
        item_xpath = '//div[@role="listitem"]/div/div[@class="card__detailsContainer-left"]'

        def next_page(self):
            if self.page.has_next:
                next_page = int(Env("page")(self)) + 1
                return BrowserURL("results", search=Env("search"), page=next_page)(self)

        class item(ItemElement):
            klass = Recipe

            obj_id = Regexp(CleanText("./a/@href"), r"https://www.allrecipes.com/recipe/(\d*)/.*/")
            obj_title = CleanText("./a/h3")
            obj_short_description = CleanText('./div[has-class("card__summary")]')


class RecipePage(HTMLPage):

    # actually, we parse the page as HTML, and lxml won't recognize utf-8-sig
    ENCODING = "utf-8"

    def build_doc(self, content):
        content = HTMLPage.build_doc(self, content)
        return json.loads(CleanText('//script[@type="application/ld+json"]')(content))[1]

    @method
    class get_recipe(ItemElement):
        klass = Recipe

        obj_id = Env("id")
        obj_title = Dict("name")
        obj_short_description = Dict("description")

        def obj_preparation_time(self):
            duration = AllRecipesDuration(Dict("prepTime"))(self)
            return int(duration.total_seconds() / 60)

        def obj_cooking_time(self):
            duration = AllRecipesDuration(Dict("cookTime"))(self)
            return int(duration.total_seconds() / 60)

        def obj_nb_person(self):
            nb_pers = "%s" % Dict("recipeYield", default="")(self)
            return [nb_pers] if nb_pers else NotAvailable

        def obj_ingredients(self):
            return [el for el in Dict("recipeIngredient")(self)]

        def obj_instructions(self):
            ins = [Dict("text")(el) for el in Dict("recipeInstructions")(self)]
            return Join("\n * ", ins, addBefore=" * ", addAfter="\n")(self)

        class obj_picture(ItemElement):
            klass = BaseImage

            obj_url = Dict("image/url")
            obj_thumbnail = Eval(Thumbnail, obj_url)

    @method
    class get_comments(DictElement):
        item_xpath = "review"

        class item(ItemElement):
            klass = Comment

            obj_author = Dict("author/name")
            obj_rate = Dict("reviewRating/ratingValue")
            obj_text = Dict("reviewBody")
            obj_id = Dict("datePublished")
