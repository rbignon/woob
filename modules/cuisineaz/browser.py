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


from woob.browser import URL, PagesBrowser

from .pages import RecipePage, ResultsPage


__all__ = ["CuisineazBrowser"]


class CuisineazBrowser(PagesBrowser):

    BASEURL = "https://www.cuisineaz.com"
    TIMEOUT = 20
    search = URL(r"recettes/recherche_terme.aspx\?recherche=(?P<pattern>.*)", ResultsPage)
    recipe = URL("recettes/(?P<id>.*).aspx", RecipePage)

    def iter_recipes(self, pattern):
        return self.search.go(pattern=pattern).iter_recipes()

    @recipe.id2url
    def get_recipe(self, url, obj=None):
        self.location(url)
        assert self.recipe.is_here()
        recipe = self.page.get_recipe(obj=obj)
        recipe.comments = list(self.get_comments(url))
        return recipe

    @recipe.id2url
    def get_comments(self, url):
        if not self.recipe.is_here():
            self.location(url)
            assert self.recipe.is_here()

        assert self.recipe.is_here()
        return self.page.get_comments()
