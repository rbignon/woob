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

from functools import wraps
import re

from woob.browser.browsers import (
    LoginBrowser, StatesMixin, need_login as optional_login,
)
from woob.browser.url import URL
from woob.capabilities.picross import PicrossNotFound, PicrossSolvedStatus
from woob.exceptions import BrowserIncorrectPassword, BrowserUnavailable

from .pages import (
    HomePage, LoginCallbackPage, LoginPage, PuzzleListPage, PuzzlePage,
    PuzzleSubmitPage, TodoPage,
)

__all__ = ['PixNCrossBrowser']

# Data required for the obfuscation method.
SYS4 = (
    '\\\'\"$ -!#%&()*,./:;?@[]^_`{|}~¡¦¨¯´¸¿+<=>±«»×÷¢£¤¥§©¬®°µ¶·0¼½¾1¹2²3³456'
    + '789aAªáÁàÀâÂäÄãÃåÅæÆbBcCçÇdDðÐeEéÉèÈêÊëËfFfgGhHiIíÍìÌîÎïÏjJkKlLmMnNñÑoO'
    + 'ºóÓòÒôÔöÖõÕøØpPqQrRsSßtTþÞuUúÚùÙûÛüÜvVwWxXyYýÝÿzZ'
)
SYS5 = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'


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

    login = URL(r'visite.php', LoginPage)
    login_callback = URL(r'action_connexion.php', LoginCallbackPage)

    home = URL(r'visite.php', HomePage)
    todo = URL(r'visite.php', TodoPage)
    puzzle_list = URL(r'visite.php', PuzzleListPage)
    puzzle = URL(r'visite.php', PuzzlePage)
    submit = URL(r'action_cid506.php', PuzzleSubmitPage)

    @staticmethod
    def obfuscate(text):
        """
        Obfuscate the given text the same way the site does.

        This algorithm is used to obfuscate text in various places, notably
        the login and password in the cookies, and some puzzle data so that
        any user cannot see the solution or other elements when opening
        the page source.

        Note that while most characters will yield two characters with such
        an algorithm, characters that are not in the SYS4 array will simply
        yield 'v'. This is because to obtain the position, the Javascript
        code uses String.prototype.indexOf, which returns -1 if the character
        is not found; while the division per 32 should return no character,
        the modulo gives 31, and 'v' is SYS5[31].

        Equivalent of t2c() in system_v1.js.
        """

        def get_code(letter):
            code = SYS4.find(letter)
            if code < 0:
                return SYS5[code % 32]

            return SYS5[code // 32:][:1] + SYS5[code % 32]

        return ''.join(map(get_code, text))

    @staticmethod
    def naive_deobfuscate(obfuscated_text):
        """
        De-obfuscate the given obfuscated text the same way the site does.

        This reverses the algorithm described previously, but supposes
        there are no unknown characters that have been replaced by 'v'.

        Equivalent of c2t() in system_v1.js.
        """

        return ''.join(
            SYS4[SYS5.find(c1) * 32 + SYS5.find(c2)]
            for c1, c2 in zip(obfuscated_text[::2], obfuscated_text[1::2])
        )

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
        self.session.cookies.set('c0', self.obfuscate(self.username))
        self.session.cookies.set('c1', self.obfuscate(self.password))
        self.page.do_login(self.username, self.password)

        if self.login_callback.is_here():
            error = self.page.get_error_message()
            if error:
                # The error message on this page is generic and not
                # very helpful.
                raise BrowserIncorrectPassword()

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

    @optional_login
    def iter_puzzles(self, solved_status):
        # Get the daily puzzle.
        self.puzzle.go(params={
            'pag': 'cid506',
            'idf': '3',
        })

        if self.page.is_solved():
            if solved_status in (
                PicrossSolvedStatus.UNKNOWN,
                PicrossSolvedStatus.SOLVED,
            ):
                self.puzzle.go(params={
                    'pag': 'cid506',
                    'idf': '3',
                    'idm': 'r',
                })
                yield self.page.get_puzzle()
        elif solved_status in (
            PicrossSolvedStatus.UNKNOWN,
            PicrossSolvedStatus.UNSOLVED,
        ):
            yield self.page.get_puzzle()

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
        """
        Go to a puzzle's page with a given id.
        """

        # Endpoints for other puzzles and daily puzzles are the same,
        # except idm is either not provided, empty or 'r' only for
        # daily puzzles, and the identifier or 'r' followed by the identifier
        # for other puzzles.
        #
        # Examples:
        #
        #    ?pag=cid506&idf=3
        #        Daily puzzle.
        #
        #    ?pag=cid506&idf=3&idm=
        #        Daily puzzle (equivalent to the above).
        #
        #    ?pag=cid506&idf=3&idm=r
        #        Daily puzzle (replay forced).
        #
        #    ?pag=cid506&idf=3&idm=123
        #        Other puzzle with identifier 123.
        #
        #    ?pag=cid506&idf=3&idm=r123
        #        Other puzzle with identifier 123 (replay forced).
        #
        m = re.fullmatch(r'(aut|pic)(\d+)', id_)
        if m is None:
            raise PicrossNotFound()

        typ = m.group(1)
        idm = m.group(2)

        if typ == 'pic':
            idm = ''

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
        if self.page.is_solved():
            self.puzzle.go(params={
                'pag': 'cid506',
                'idf': '3',
                'idm': 'r' + idm,
            })

        # What we have on the daily picross page might not correspond
        # to the puzzle we're trying to go to.
        actual_puzzle_id = self.page.get_puzzle_id()
        if actual_puzzle_id != id_:
            if typ == 'pic' and actual_puzzle_id.startswith('pic'):
                raise BrowserUnavailable(
                    "The picross you are trying to access is not today's "
                    + f"daily picross! (current: {actual_puzzle_id!r}, "
                    + f'requested: {id_!r}).',
                )

            raise AssertionError(
                'Found picross has identifier '
                + f'{actual_puzzle_id!r}, not {id_!r}.',
            )

    @optional_login
    def get_puzzle(self, id_):
        self._go_to_puzzle(id_)
        return self.page.get_puzzle()

    @need_login
    def submit_solution(self, id_, solution):
        self._go_to_puzzle(id_)
        return self.page.submit_solution(solution)
