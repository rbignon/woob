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

import re

from woob.browser.elements import ItemElement, ListElement, method
from woob.browser.filters.html import Attr, Link
from woob.browser.filters.standard import BrowserURL, CleanText, Env, Field, Format, Regexp
from woob.browser.pages import HTMLPage, pagination
from woob.capabilities.picross import Picross, PicrossSolvedStatus, PicrossVariant


def get_color(expr):
    """
    Get an integer representing an sRGB color from an expression.
    """

    m = re.search(r'rgb\((?P<r>\d+), (?P<g>\d+), (?P<b>\d+)\)', expr)
    if m:
        return (
            int(m.group('r')) * 65535
            + int(m.group('g')) * 255
            + int(m.group('b'))
        )

    m = re.search(r'#([0-9A-Fa-f]{6})', expr)
    if m:
        return int(m.group(1), 16)

    raise ValueError(f'Could not decode color from expression {expr!r}!')


class NonogramListPage(HTMLPage):
    @pagination
    @method
    class iter_nonograms(ListElement):
        item_xpath = '//div[@id="catitems"]/div'

        # * //div[@class="pages"] has two instances, one at the top of the
        #   page and one at the bottom page; we take the top one.
        # * Always contains three spans, middle one being current page,
        #   first one being pagination before current page, last one
        #   being pagination after current page.
        #   We take the first link of the third section, i.e. the first
        #   link of the pagination after the current page.
        next_page = Link(
            '//div[@class="pages"][1]/span[3]/a[1]',
            default=None,
        )

        class item(ItemElement):
            klass = Picross

            obj_id = Regexp(Link('.//a'), r'^/?(\d+)$')
            obj_url = BrowserURL('nonogram', nonogram_id=Field('id'))
            obj_name = Format('Nonogram #%s', Field('id'))
            obj_variant = PicrossVariant.COLORED
            obj_solved_status = PicrossSolvedStatus.UNSOLVED


class NonogramPage(HTMLPage):
    @method
    class get_nonogram(ItemElement):
        klass = Picross

        def parse(self, el):
            columns = []
            column_colors = []

            for col_no, top_line in enumerate(
                el.xpath('//table[@id="cross_top"]//tr'),
            ):
                top_cells = list(top_line.xpath('./td'))

                # If we have the first line here, we adapt the number of
                # columns following the number of cells.
                # Otherwise, we check if we have the same number of cells;
                # we should, otherwise that means one line is longer than
                # another.
                if col_no == 0:
                    columns = [[] for _ in range(len(top_cells))]
                    column_colors = [[] for _ in range(len(columns))]
                elif len(top_cells) != len(columns):
                    raise AssertionError('Inconsistent number of columns')

                for top_cell, col, color_col in zip(
                    top_cells,
                    columns,
                    column_colors,
                ):
                    # Get the number in the cell.
                    number = CleanText('.')(top_cell)
                    if number:
                        number = int(number)
                    elif col:
                        # We've already picked up a number for this column,
                        # which means there was a gap in the column
                        # definition; this shouldn't happen.
                        raise AssertionError('Gap in column while parsing')
                    else:
                        # We haven't reached actual numbers for this column
                        # yet, so let's continue.
                        continue

                    number = int(number)

                    # Find out which color the cell corresponds to, if there
                    # actually is a color.
                    background_color = Regexp(
                        Attr('.', 'style'),
                        r'background-color: ([^;]+);',
                        default='#E0E0E0',
                    )(top_cell)

                    color = get_color(background_color)

                    # We're good!
                    col.append(number)
                    color_col.append(color)

            raw_rows = list(el.xpath('//table[@id="cross_left"]//tr'))

            rows = [[] for _ in range(len(raw_rows))]
            row_colors = [[] for _ in range(len(rows))]

            for raw_row, row, color_row in zip(
                raw_rows,
                rows,
                row_colors,
            ):
                for row_cell in raw_row.xpath('./td'):
                    # Get the number in the cell.
                    number = CleanText('.')(row_cell)
                    if number:
                        number = int(number)
                    elif row:
                        # We've already picked up a number for this row,
                        # which means there was a gap in the row
                        # definition; this shouldn't happen.
                        raise AssertionError('Gap in row while parsing')
                    else:
                        # We haven't reached actual numbers for this row
                        # yet, so let's continue.
                        continue

                    number = int(number)

                    # Find out which color the cell corresponds to, if there
                    # actually is a color.
                    background_color = Regexp(
                        Attr('.', 'style'),
                        r'background-color: ([^;]+)(;|$)',
                        default='#E0E0E0',
                    )(row_cell)

                    color = get_color(background_color)

                    # We're good!
                    row.append(number)
                    color_row.append(color)

            self.env['rows'] = rows
            self.env['columns'] = columns

            self.env['variant'] = PicrossVariant.BASIC

            for _ in self.el.xpath('//button[@class="color_button bc_2"]'):
                # A second primary color is present for selecting,
                # so the picross is a colored picross!
                self.env['variant'] = PicrossVariant.COLORED
                self.env['row_colors'] = row_colors
                self.env['column_colors'] = column_colors
                break

        obj_id = Regexp(
            CleanText('//script[contains(., "currentID=")]'),
            r'currentID=(\d+);',
        )
        obj_url = BrowserURL('nonogram', nonogram_id=Field('id'))
        obj_name = Format('Nonogram #%s', Field('id'))
        obj_variant = Env('variant')
        obj_solved_status = PicrossSolvedStatus.UNSOLVED

        obj_lines = Env('rows')
        obj_columns = Env('columns')
        obj_color_lines = Env('row_colors', default=None)
        obj_color_columns = Env('column_colors', default=None)
