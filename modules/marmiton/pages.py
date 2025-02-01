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

from woob.browser.elements import DictElement, ItemElement, method
from woob.browser.filters.html import XPath
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import BrowserURL, CleanDecimal, CleanText, Env, Eval, Format, Regexp
from woob.browser.pages import HTMLPage, JsonPage, pagination
from woob.capabilities.base import NotAvailable
from woob.capabilities.image import BaseImage, Thumbnail
from woob.capabilities.recipe import Comment, Recipe
from woob.tools.json import json


class ResultsPage(HTMLPage):
    """Page which contains results as a list of recipies"""

    ENCODING = "utf-8"

    def build_doc(self, content):
        content = HTMLPage.build_doc(self, content)
        return json.loads(CleanText('//script[@id="__NEXT_DATA__"]')(content))

    @pagination
    @method
    class iter_recipes(DictElement):
        item_xpath = "props/pageProps/searchResults/hits"

        def next_page(self):
            current_page = int(Env("page")(self))
            if Dict("props/pageProps/searchResults/nbPages")(self) >= current_page:
                return BrowserURL("search", pattern=Env("pattern"), start=Env("start"), page=current_page + 1)(self)

        class item(ItemElement):
            klass = Recipe
            obj_id = Regexp(Dict("url"), "/recettes/recette_(.*).aspx")
            obj_title = Dict("title")
            obj_short_description = Format(
                "%s - %s - Nutriscore : %s - Note : %s/5",
                Dict("dishType"),
                Dict("cookingType"),
                Dict("nutriScore"),
                Dict("averageRating"),
            )
            obj_ingredients = Dict("ingredients")

            class obj_picture(ItemElement):
                klass = BaseImage

                obj_url = Dict("image/pictureUrls/origin", default=NotAvailable)

                def obj_thumbnail(self):
                    return Eval(Thumbnail, self.obj_url)(self)

        def obj_preparation_time(self):
            return Dict("preparationTime")(self) / 60

        def obj_cooking_time(self):
            return Dict("cookingTime")(self) / 60


class RecipePage(HTMLPage):
    """Page which contains a recipe"""

    @method
    class get_recipe(ItemElement):
        klass = Recipe

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            items = XPath('//script[@type="application/ld+json"]')(self.el)

            for item in items:
                content = json.loads(CleanText(".")(item))
                if content["@type"] == "Recipe":
                    self.el = content
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

        def obj_instructions(self):
            instructions = ""
            for item in Dict("recipeInstructions")(self):
                instructions = "{} - {}\n\n".format(instructions, item["text"])
            return instructions

        obj_preparation_time = Eval(int, CleanDecimal(Dict("prepTime")))
        obj_cooking_time = Eval(int, CleanDecimal(Dict("cookTime")))

        def obj_nb_person(self):
            return [Dict("recipeYield")(self)]


class CommentsPage(JsonPage):
    """Page which contains a comments"""

    @method
    class get_comments(DictElement):
        item_xpath = "reviews"

        class item(ItemElement):
            klass = Comment

            obj_author = Dict("username")
            obj_rate = CleanText(Dict("rating"))
            obj_text = Dict("content")
            obj_id = Dict("reviewId")
