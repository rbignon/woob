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
import re

from woob.browser import URL, PagesBrowser

from .pages import CommentsPage, RecipePage, ResultsPage


__all__ = ["MarmitonBrowser"]


class MarmitonBrowser(PagesBrowser):
    BASEURL = "https://www.marmiton.org"
    search = URL(
        r"/recettes/recherche.aspx\?aqt=(?P<pattern>.*)&start=(?P<start>\d*)&page=(?P<page>\d*)",
        r"/recettes/recherche.aspx\?aqt=.*",
        ResultsPage,
    )
    recipe = URL(r"/recettes/recette_(?P<id>.*).aspx", RecipePage)
    comment = URL(r"https://api-uno.marmiton.org/origin/(?P<_id>\d*)/top-reviews\?originType=RECIPE", CommentsPage)

    def iter_recipes(self, pattern):
        return self.search.go(pattern=pattern, start=0, page=0).iter_recipes(pattern=pattern)

    @recipe.id2url
    def get_recipe(self, url, recipe=None):
        self.location(url)
        assert self.recipe.is_here()
        recipe = self.page.get_recipe(obj=recipe)

        m = re.match(r".*_(\d*)$", recipe.id, re.DOTALL)
        if m:
            _id = m.group(1)
            self.session.headers["x-site-id"] = "13"
            comments = list(self.comment.go(_id=_id).get_comments())
            if comments:
                recipe.comments = comments
            return recipe
