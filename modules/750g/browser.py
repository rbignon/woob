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

from woob.browser import PagesBrowser, URL
from .pages import RecipePage, ResultsPage, CommentPage
from woob.tools.compat import quote_plus


__all__ = ['SevenFiftyGramsBrowser']


class SevenFiftyGramsBrowser(PagesBrowser):
    BASEURL = 'https://www.750g.com'

    comment = URL('/recipe/(?P<_id>.*)/sort/lastest/comments.json', CommentPage)
    search = URL(r'/recherche/\?q=(?P<pattern>.*)&page=(?P<page>\d*)', ResultsPage)
    recipe = URL('/(?P<id>.*).htm', RecipePage)

    def iter_recipes(self, pattern):
        return self.search.go(pattern=quote_plus(pattern.encode('utf-8')), page=1).iter_recipes()

    def get_recipe(self, id, recipe=None):
        self.recipe.go(id=id)
        return self.get_recipe_content(recipe)

    def get_comments(self, id):
        m = re.match(r'.*r(\d*)', id, re.DOTALL)
        if m:
            _id = m.group(1)
            return self.comment.go(_id=_id).get_comments()

    def get_recipe_content(self, recipe=None):
        recipe = self.page.get_recipe(obj=recipe)
        comments = self.get_comments(recipe.id)
        if comments:
            recipe.comments = list(comments)
        return recipe
