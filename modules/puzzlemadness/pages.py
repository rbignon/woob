# flake8: compatible

# Copyright(C) 2022 Thomas Touhey <thomas@touhey.fr>
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

from woob.browser.elements import ItemElement, TableElement, method
from woob.browser.filters.html import Link, TableCell, XPath
from woob.browser.filters.standard import (
    BrowserURL, CleanText, Env, Field, Format, Regexp,
)
from woob.browser.pages import HTMLPage
from woob.capabilities.picross import Picross, PicrossSolvedStatus
from woob.tools.json import json


class SubXPath(XPath):
    def __init__(self, selector, xpath, *args, **kwargs):
        super().__init__(selector, *args, **kwargs)
        self.sub_xpath = xpath

    def _subselect(self, ret):
        """
        Iterator for selecting elements in the given return using the xpath.
        """

        if not isinstance(ret, (tuple, list)):
            ret = (ret,)

        for element in ret:
            for subelement in element.xpath(self.sub_xpath):
                yield subelement

    def select(self, *args, **kwargs):
        return list(
            self._subselect(super().select(*args, **kwargs)),
        )


class PicrossListPage(HTMLPage):
    @method
    class iter_picrosses(TableElement):
        # NOTE: This page has no pagination for picrosses, everything seems
        #       to be on the main page (it's a really long page).

        head_xpath = '//th[@class="picross-puzzle-list__table-heading"]'
        item_xpath = '//tr[./td[@class="picross-puzzle-list__puzzle-title"]]'

        col_title = 'Title'
        col_size = 'Size'
        col_rating = 'Rating'

        class item(ItemElement):
            klass = Picross

            obj_id = Format(
                'p%s',
                Regexp(
                    Link(SubXPath(TableCell('title'), './a')),
                    r'picross/(\d+)',
                ),
            )
            obj_name = CleanText(TableCell('title'))
            obj_solved_status = PicrossSolvedStatus.UNSOLVED


class PicrossPage(HTMLPage):
    @method
    class get_picross(ItemElement):
        klass = Picross

        def parse(self, el):
            puzzledata = json.loads(
                Regexp(
                    CleanText('//script[contains(., "var puzzledata")]'),
                    r'var puzzledata = ({.+?});',
                )(el),
            )

            self.env['id'] = puzzledata['data']['index']
            self.env['lines'] = [
                tuple(line) for line in puzzledata['data']['horizontalClues']
            ]
            self.env['columns'] = [
                tuple(col) for col in puzzledata['data']['verticalClues']
            ]

        obj_id = Format('p%s', Env('id'))
        obj_url = BrowserURL('picross', picross_id=Field('id'))
        obj_name = Regexp(CleanText('//head/title'), r'Picross: (.+)')
        obj_lines = Env('lines')
        obj_columns = Env('columns')
        obj_solved_status = PicrossSolvedStatus.UNSOLVED
