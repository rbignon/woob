# Copyright(C) 2018      Phyks (Lucas Verney)
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
from woob.browser.filters.html import Attr, Link, XPath
from woob.browser.filters.standard import CleanDecimal, CleanText, Env, Eval, Join, Regexp
from woob.browser.pages import HTMLPage
from woob.capabilities.base import NotAvailable
from woob.capabilities.image import BaseImage, Thumbnail
from woob.capabilities.recipe import Comment, Recipe


class SearchPage(HTMLPage):
    """
    Page which contains search results
    """

    @method
    class get_recipes(ListElement):
        item_xpath = '//li[has-class("bu_cuisine_mod_search__result")]'

        class item(ItemElement):
            klass = Recipe

            obj_id = Regexp(Link('.//a[has-class("bu_cuisine_recette_img")]'), r".*\/(.*)$")

            obj_url = Link('.//a[has-class("bu_cuisine_recette_img")]')
            obj_title = CleanText('.//p[has-class("bu_cuisine_recette_title")]')
            obj_short_description = NotAvailable
            obj_author = NotAvailable
            obj_ingredients = NotAvailable

            class obj_picture(ItemElement):
                klass = BaseImage

                obj_url = NotAvailable

                def obj_thumbnail(self):
                    style = Attr('.//a[has-class("bu_cuisine_recette_img")]/span', "style")(self)
                    return Thumbnail(style.replace("background-image:url(", "").rstrip(");"))

            obj_instructions = NotAvailable

            def obj_preparation_time(self):
                prep_time = CleanDecimal('(.//span[has-class("bu_cuisine_recette_carnet_duree")])[1]', default=0)(self)
                return int(prep_time)

            def obj_cooking_time(self):
                cooking_time = CleanDecimal('(.//span[has-class("bu_cuisine_recette_carnet_duree")])[2]', default=0)(
                    self
                )
                return int(cooking_time)

            obj_nb_person = NotAvailable


class RecipePage(HTMLPage):
    """
    Page which contains a recipe
    """

    @method
    class get_recipe(ItemElement):
        klass = Recipe

        obj_id = Env("id")
        obj_title = CleanText('//article[has-class("bu_cuisine_main_recipe")]/header/h1')
        obj_short_description = CleanText('//p[@class="app_recipe_legend"]|//p[has-class("bu_cuisine_legende_italic")]')
        obj_author = CleanText('//h3[has-class("app_recipe_author_name")]')

        def obj_ingredients(self):
            ingredients_items = XPath('//ul[has-class("app_recipe_list")]/li|//ul[@class="bu_cuisine_ingredients"]/li')(
                self
            )
            return [CleanText(".")(ingredients_item) for ingredients_item in ingredients_items]

        class obj_picture(ItemElement):
            klass = BaseImage

            obj_url = Attr('//div[has-class("jVideoFirstImg")]' '//img[has-class("bu_cuisine_img_noborder")]', "src")
            obj_thumbnail = Eval(Thumbnail, obj_url)

        obj_instructions = Join(
            "\n- ",
            '//div[@class="grid_line"]/ol/li[has-class("bu_cuisine_recette_prepa")]',
            newline=True,
            addBefore="- ",
        )

        def obj_preparation_time(self):
            prep_time = CleanDecimal(
                '//div[has-class("app_recipe_resume")]/div[2]|//ul[@class="bu_cuisine_carnet_2"]/li[2]', default=0
            )(self)
            return int(prep_time)

        def obj_cooking_time(self):
            cooking_time = CleanDecimal(
                '//div[has-class("app_recipe_resume")]/div[3]|//ul[@class="bu_cuisine_carnet_2"]/li[3]', default=0
            )(self)
            return int(cooking_time)

        def obj_nb_person(self):
            nb_person = CleanText('//span[@id="numberPerson"]')(self)

            if not nb_person:
                nb_person = CleanDecimal('//span[@class="bu_cuisine_title_3 bu_cuisine_title_3--subtitle"]')(self)
            return [str(nb_person)]

    @method
    class get_comments(ListElement):
        item_xpath = '//div[has-class("bu_cuisine_avis")]'

        class item(ItemElement):
            klass = Comment

            obj_id = Regexp(Link('./span[has-class("bu_cuisine_signaler_lnk")]/a'), r".*#(.*)\|.*$")

            obj_author = CleanText('.//span[has-class("bu_cuisine_avis_auteur")]', children=False)

            obj_text = CleanText("./p")

            def obj_rate(self):
                return str(len(XPath('.//span[@class="app_rating_star"]/svg[@fill="#f6303e"]')(self)))
