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

from urllib.parse import parse_qsl, urlencode, urlparse

from woob.browser.elements import ItemElement, ListElement, method
from woob.browser.filters.html import Attr, Link
from woob.browser.filters.standard import CleanText, Env, Format, Map, Regexp
from woob.browser.pages import HTMLPage, pagination
from woob.capabilities.picross import (
    Picross, PicrossNotFound, PicrossSolvedStatus,
)


class BasePage(HTMLPage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Most base pages use GET parameters to check whether they
        # correspond to the current page using the URL; we're better
        # off parsing the arguments right away.
        self.params = dict(parse_qsl(urlparse(self.url).query))
        self.page_id = self.params.get('pag')

        # To check if the user is logged in, we want to check whether
        # the box at the top contains "Connecté : <username>" instead
        # of the other buttons to log in or register.
        self.logged = False
        for _ in self.doc.xpath(
            '//div[@class="insc" and contains(., "Connecté")]',
        ):
            self.logged = True
            break


class HomePage(BasePage):
    def is_here(self):
        # The home page is returned by default, so we do not want to
        # match it using what's in the GET parameters, but directly
        # with what's in the page.
        for _ in self.doc.xpath(
            # Currently the h1 is "Page d'acceuil" (sic), but we want
            # to manage the day where this typo might be fixed.
            '//h1[contains(., "acceuil") or contains(., "accueil")]',
        ):
            return True
        return False


class LoginPage(BasePage):
    def is_here(self):
        return self.page_id == 'connexion'

    def do_login(self, username, password):
        form = self.get_form('//form[@name="frm"]')
        form['lgt'] = username
        form['pwt'] = password
        form.submit()


class LoginCallbackPage(HTMLPage):
    # Can redirect on successful login using Refresh http-equiv meta tag.
    REFRESH_MAX = 3

    def get_error_message(self):
        return CleanText(
            '//div[@class="g0" and contains(@style, "background-image")]',
            default='',
        ) or None


class TodoPage(BasePage):
    def is_here(self):
        return self.page_id == 'cid506_todo'

    def is_incomplete(self):
        """
        Check if there are more than 200 references, in which case the
        list will be incomplete.
        """

        for _ in self.doc.xpath(
            # "etc... (cette liste contient plus de 200 références)"
            '//div[@class="d2" and contains(., "contient plus de")]',
        ):
            return True

        return False

    @pagination
    @method
    class iter_puzzles(ListElement):
        item_xpath = '//div[@class="d2"]/a[@class="l1"]'

        class item(ItemElement):
            klass = Picross

            def parse(self, el):
                # Parse the identifier from the URL, to be safe.
                params = dict(parse_qsl(urlparse(Link('.')(el)).query))
                self.env['id'] = params['idm']

            obj_id = Format('aut%s', Env('id'))
            obj_solved_status = PicrossSolvedStatus.UNSOLVED


class PuzzleListPage(BasePage):
    def is_here(self):
        return (
            self.page_id in ('cid506_picross', 'cid506_picross_new')
            and 'idd' in self.params
        )

    @pagination
    @method
    class iter_puzzles(ListElement):
        item_xpath = '//div[@class="d1"]/div[@class="d2"]/div[@class="z000"]'

        def next_page(self):
            # For pages 1 to 9, the prefix 'Page ' is present, but
            # at page 10 and beyond, this div only contains e.g.
            # '10/233' directly.
            full_page = Regexp(
                CleanText(
                    '//div[@class="z000"]//span[@class="t5"]',
                    default='',
                ),
                r'(\d+/\d+)',
                default=None,
            )(self.el)

            if full_page is None:
                return

            current_page, last_page = map(int, full_page.split('/'))
            if current_page >= last_page:
                return

            # We want to get the page after.
            parsed_url = urlparse(self.page.url)
            parsed_params = dict(parse_qsl(parsed_url.query))
            parsed_params['npa'] = str(current_page + 1)

            return parsed_url._replace(
                query=urlencode(parsed_params, doseq=True),
            ).geturl()

        class item(ItemElement):
            klass = Picross

            def condition(self):
                # Get the solved status by checking if the background
                # image is set on the text to display the 'solved' icon
                # instead of the default 'unsolved' icon.
                custom_style = Attr(
                    './div[@class="g0"]',
                    'style',
                    default=None,
                )(self.el)
                solved_status = PicrossSolvedStatus.UNSOLVED
                if custom_style is not None:
                    solved_status = PicrossSolvedStatus.SOLVED

                queried_status = self.env['queried_solved_status']
                if queried_status not in (
                    PicrossSolvedStatus.UNKNOWN,
                    solved_status,
                ):
                    return False

                # Store the solved status for later computing.
                self.env['solved_status'] = solved_status
                return True

            def parse(self, el):
                # Get the picross identifier from the link to it.
                url = Link('.//b/a')(el)
                params = dict(parse_qsl(urlparse(url).query))
                if 'idm' not in params:
                    raise AssertionError("Could not get the puzzle's id.")

                self.env['id'] = params['idm'].lstrip('r')

            obj_id = Format('aut%s', Env('id'))
            obj_solved_status = Env('solved_status')


class PuzzlePage(BasePage):
    def on_load(self):
        # The page could be a 'solved' page, which makes that the
        # puzzle data is not present on the page but a message saying
        # the message has been solved is present, with a link to retry,
        # which is the same page but with the puzzle identifier being
        # prefixed with an 'r'.
        self.solved = False

        for _ in self.doc.xpath(
            '//div[@class="g0"and contains(., "en résolvant")]',
        ):
            self.solved = True

        # 'Invalid' references will still result in more or less valid
        # pages being returned, except the pattern is simply '%'.
        # We want to catch this and store it, just in case.
        if not self.solved:
            self.pattern = Regexp(
                CleanText('//script[contains(., "var e506a")]'),
                r"var e506a = '([^']+)'",
            )(self.doc)

            if self.pattern == '%':
                raise PicrossNotFound()

        # We want to store the full identifier of the puzzle here in order
        # to be able to use it in both `get_puzzle_id` and `get_puzzle`.
        self.puzzle_id = None
        if not self.solved:
            self.puzzle_id = Format(
                '%s%s',
                Attr('//form[@name="frm"]/input[@name="idtableau"]', 'value'),
                Attr('//form[@name="frm"]/input[@name="idligne"]', 'value'),
            )(self.doc)

    def is_here(self):
        return self.page_id == 'cid506'

    def is_solved(self):
        return self.solved

    def get_puzzle_id(self):
        return self.puzzle_id

    @method
    class get_puzzle(ItemElement):
        klass = Picross

        def condition(self):
            return not self.page.solved

        def parse(self, el):
            self.env['id'] = self.page.puzzle_id

            if self.page.params.get('idm') not in (None, '', 'r'):
                self.env['url'] = self.page.url

            def get_line(raw_value):
                """
                Get a value for a line or a column.

                Raw value here is either empty or numbers
                separated by solidus ('/').
                """

                if not raw_value:
                    return ()  # '0'
                return tuple(map(int, raw_value.split('/')))

            columns, lines = self.page.pattern.split('%')
            self.env['columns'] = list(map(get_line, columns.split('_')))
            self.env['lines'] = list(map(get_line, lines.split('_')))

            # To check if we are on replay, we want to look at the
            # identifier in the URL.
            idm = self.page.params.get('idm')
            self.env['is_replay'] = bool(idm and idm.startswith('r'))

        obj_id = Env('id')
        obj_url = Env('url', default=None)
        obj_lines = Env('lines')
        obj_columns = Env('columns')

        obj_solved_status = Map(
            Env('is_replay'),
            {
                False: PicrossSolvedStatus.UNSOLVED,
                True: PicrossSolvedStatus.SOLVED,
            },
        )

    def submit_solution(self, solution):
        # Here, we submit a historic of our moves, as a '/' joined array where:
        #
        # * The first element is '_'.
        # * Every other element is formatted as 'XXYYT11', where:
        #
        #   - XX is the X coordinate, padded with zeroes, e.g. '02' or '11'.
        #   - YY is the Y coordinate, padded with zeroes, e.g. '02' or '11'.
        #   - T is the character representing the type of action, here:
        #
        #     * 'c' is placing a cross (empty space).
        #     * 'b' is placing a full block (full space).
        #   - 11 is constant.
        #
        # Example actions are the following:
        #
        # - 0105b11: place a block at x=1, y=5.
        # - 0414c11: place a cross at x=4, y=14.
        #
        # The history cancels itself, i.e. you have no "cross/block removed"
        # action here, you only technically have the order in which the
        # elements are definitively placed.
        #
        # Here, we'll just consider the 'player' has placed every block
        # from up to down, left to right (occidental fashion, heck yeah).
        moves = '_/' + '/'.join(
            f'{x:02d}{y:02d}{"cb"[c == "x"]}11'
            for y, line in enumerate(solution.lines)
            for x, c in enumerate(line)
        )

        form = self.get_form('//form[@name="frm"]')
        form['histo'] = moves
        form['aide'] = '0'
        form['fini'] = '1'
        form.submit()


class PuzzleSubmitPage(HTMLPage):
    # Can redirect on successful login using Refresh http-equiv meta tag.
    REFRESH_MAX = 3
