# flake8: compatible

# Copyright(C) 2022-2024 Thomas Touhey <thomas@touhey.fr>
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
from functools import wraps

from woob.browser.browsers import LoginBrowser, StatesMixin
from woob.browser.browsers import need_login as optional_login
from woob.browser.url import URL
from woob.capabilities.picross import PicrossNotFound, PicrossSolvedStatus
from woob.exceptions import BrowserIncorrectPassword, BrowserUnavailable

from .pages import (
    DailyPicrossListPage, HiddenFormPage, HomePage, LoginCallbackPage, LoginPage, PuzzleListPage, PuzzlePage,
    PuzzleSubmitPage, TodoPage,
)
from .utils import obfuscate


__all__ = ['PixNCrossBrowser']


def need_login(func):
    @wraps(func)
    def decorated_func(browser, *args, **kwargs):
        if not browser.username:
            raise BrowserIncorrectPassword(
                'This action cannot be done anonymously.',
            )

        return func(browser, *args, **kwargs)

    return optional_login(decorated_func)


class PixNCrossBrowser(LoginBrowser, StatesMixin):
    BASEURL = 'https://www.pix-n-cross.com/'

    hidden_form = URL(r'', HiddenFormPage)

    login = URL(r'visite.php', LoginPage)
    login_callback = URL(r'action_connexion.php', LoginCallbackPage)

    home = URL(
        r'$',
        r'\?',
        r'visite.php',
        HomePage,
    )
    todo = URL(r'\?', r'visite.php', TodoPage)
    puzzle_list = URL(r'\?', r'visite.php', PuzzleListPage)
    daily_picross_list = URL(r'\?', r'visite.php', DailyPicrossListPage)
    puzzle = URL(r'\?', r'visite.php', PuzzlePage)
    submit = URL(r'action_cid506.php', PuzzleSubmitPage)

    def do_login(self):
        if not self.username and not self.password:
            return  # No login required.
        if not self.username or not self.password:
            raise BrowserIncorrectPassword('Missing username or password.')

        self.login.go(params={'pag': 'connexion'})

        # We set our cookies ourselves here.
        # This is because the authentication on pix-n-cross is accomplished
        # by sending the obfuscated username and password on EVERY REQUEST.
        # This page barely serves to verify that the username and password
        # are valid.
        self.session.cookies.set('c0', obfuscate(self.username))
        self.session.cookies.set('c1', obfuscate(self.password))
        self.page.do_login(self.username, self.password)

        if self.login_callback.is_here():
            error = self.page.get_error_message()
            if error:
                # The error message on this page is generic and not
                # very helpful.
                raise BrowserIncorrectPassword()

        if self.hidden_form.is_here():
            self.page.submit_hidden_form()

        if not self.home.is_here():
            raise AssertionError('Should be on home page')

    # NOTE: There are several types of puzzles, each identified by a three
    #       letter prefix we put in front on the identified:
    #
    # +========+=============================================================+
    # | Prefix | Description                                                 |
    # +========|=============================================================+
    # | pic    | Daily puzzles: these are only accessible on the day they're |
    # |        | on. They all share the same URL, the identifier can be      |
    # |        | found on the page as `idligne`.                             |
    # +--------+-------------------------------------------------------------+
    # | aut    | Other puzzles: these are accessible and solvable at all     |
    # |        | times. They have individual URLs, are identified by a       |
    # |        | numeric incremental identifier, equivalent to `idm`.        |
    # +--------+-------------------------------------------------------------+
    #
    # Example identifiers are the following:
    #
    # * `pic198`: The daily puzzle from June 4th.
    # * `aut2324`: The other puzzle number 2324, published on June 3rd, 2022.
    #
    # Note that daily puzzles loop every year, and some aren't even accessible
    # every year, such as the one on Feb 29th.

    def _iter_daily_puzzles(self, solved_status):
        """Iterate over daily puzzles.

        :param solved_status: The solved status the client is looking for.
        """
        # Premium members have access to a list of daily puzzles, while
        # normal members have access to the daily puzzle directly.
        # We want to be able to distinguish between both by going on the
        # same page for both.
        self.puzzle.go(params={
            'pag': 'cid506',
            'idf': '3',
        })

        if self.daily_picross_list.is_here():
            # For premium members, this page may actually be a list of two
            # picrosses, so we want to yield both if relevant.
            # Note that we use the daily list page directly to check if the
            # daily picrosses have been resolved.
            daily_list_page = self.page
            for ids in (1, 2):
                is_solved = daily_list_page.is_daily_picross_solved(ids)

                if (
                    solved_status == PicrossSolvedStatus.SOLVED
                    and not is_solved
                ):
                    continue

                if solved_status == PicrossSolvedStatus.UNSOLVED and is_solved:
                    continue

                self.puzzle.go(params={
                    'pag': 'cid506_daily_picross',
                    'idf': '3',
                    'ids': str(ids),
                })
                self.page.go_to_unsolved_if_needed()
                yield self.page.get_puzzle()
        else:
            # For non-premium members, we have the daily picross here directly.
            is_solved = self.page.is_solved()

            if solved_status == PicrossSolvedStatus.SOLVED and not is_solved:
                return

            if solved_status == PicrossSolvedStatus.UNSOLVED and is_solved:
                return

            self.page.go_to_unsolved_if_needed()
            yield self.page.get_puzzle()

    @optional_login
    def iter_puzzles(self, solved_status):
        yield from self._iter_daily_puzzles(solved_status)

        # If we are looking for any or only solved picrosses, we will have
        # to go into the puzzle list. Otherwise, we can just go in the
        # 'unsolved puzzles' page, in which case, however, we might have
        # an incomplete list.
        use_puzzle_list = True
        if solved_status == PicrossSolvedStatus.UNSOLVED:
            self.todo.go(params={
                'pag': 'cid506_todo',
                'idf': '3',
            })

            # If the list is incomplete, nevermind, we will just go to
            # the puzzle list to list incomplete puzzles, in order to be
            # sure to have them all, since there is no pagination on
            # the todo page.
            use_puzzle_list = self.page.is_incomplete()

        if use_puzzle_list:
            self.puzzle_list.go(params={
                'pag': 'cid506_picross',
                'idf': '3',
                'idd': 'all',  # All categories.
            })

        for picross in self.page.iter_puzzles(
            queried_solved_status=solved_status,
        ):
            id_ = picross.id[3:]  # Remove the 'aut' prefix.

            # If the picross is solved, we have to add 'r' in front in order
            # to force a 'retry' to get the puzzle data.
            if picross.solved_status == PicrossSolvedStatus.SOLVED:
                id_ = 'r' + id_

            self.puzzle.go(params={
                'pag': 'cid506',
                'idf': '3',
                'idm': id_,
            })
            yield self.page.get_puzzle(picross=picross)

    def _go_to_puzzle(self, id_):
        """Go to a puzzle's page with a given id.

        Daily puzzles ("pic") and other puzzles ("aut") are treated
        differently because for some members, there are multiple daily puzzles,
        and no easy way to predict which daily puzzle corresponds to the
        identifier.
        """
        if (
            self.puzzle.is_here()
            and not self.page.solved
            and self.page.get_puzzle_id() == id_
        ):
            return

        m = re.fullmatch(r'(aut|pic)(\d+)', id_)
        if m is None:
            raise PicrossNotFound()

        typ = m.group(1)
        idm = m.group(2)

        if typ == 'pic':
            self.puzzle.go(params={
                'pag': 'cid506',
                'idf': '3',
            })

            if self.daily_picross_list.is_here():
                for ids in (1, 2):
                    self.puzzle.go(params={
                        'pag': 'cid506_daily_picross',
                        'idf': '3',
                        'ids': str(ids),
                    })
                    self.page.go_to_unsolved_if_needed()
                    if self.page.get_puzzle_id() == id_:
                        # This is the correct daily picross!
                        return
            else:
                self.page.go_to_unsolved_if_needed()
                if self.page.get_puzzle_id() == id_:
                    # This is the correct daily picross!
                    return

            raise BrowserUnavailable(
                'The picross you are trying to access is not accessible '
                + 'today!',
            )

        if typ != 'aut':
            raise PicrossNotFound()

        # Note that we won't get an HTTP 404 for a non-existent pattern,
        # we will simply get a '%' pattern, which is detected by the
        # PuzzlePage which will raise a PicrossNotFound exception.
        self.puzzle.go(params={
            'pag': 'cid506',
            'idf': '3',
            'idm': idm,
        })

        # If we have the 'resolved' page, we need to query the 'retry'
        # page in order to get the picross definition.
        self.page.go_to_unsolved_if_needed()

    @optional_login
    def get_puzzle(self, id_):
        self._go_to_puzzle(id_)
        return self.page.get_puzzle()

    @need_login
    def submit_solution(self, id_, solution):
        self._go_to_puzzle(id_)
        return self.page.submit_solution(solution)
