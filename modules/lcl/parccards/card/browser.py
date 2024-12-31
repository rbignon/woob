# Copyright(C) 2023 Powens
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

from random import randint
from time import sleep

from woob.browser.browsers import URL, LoginBrowser, need_login
from woob.browser.exceptions import ClientError
from woob.exceptions import BrowserIncorrectPassword, BrowserUserBanned

from ..pages import HistoryPage
from .pages import LoginPage, PeriodsPage


__all__ = ['LCLCardsBrowser']


class LCLCardsBrowser(LoginBrowser):
    BASEURL = 'https://cartesentreprises.secure.lcl.fr'
    TIMEOUT = 30.0

    login = URL(r'/services/users/login', LoginPage)
    periods = URL(r'/services/porteur/depensescarte', PeriodsPage)
    history = URL(r'/services/porteur/operationscarteporteur', HistoryPage)

    def __init__(self, config, *args, **kwargs):
        super(LCLCardsBrowser, self).__init__(*args, **kwargs)
        self.accounts_page = None

    def do_login(self):
        if not self.password.isdigit():
            raise BrowserIncorrectPassword()

        # Dirty hack to prevent sharing account on 2 different connections
        # if we login/list account at the same time with 2 differents login/password, the account list is
        # shared between the 2.
        sleep(randint(0, 15))

        try:
            # We can't access the accounts page later, we need to cache it
            self.accounts_page = self.login.go(json={
                'login': self.username,
                'password': self.password,
            })
        except ClientError as e:
            if e.response.text == '"USER_ACCOUNT_LOCKED_BY_TOO_MANY_WRONG_AUTHENTICATIONS"':
                raise BrowserUserBanned('Trop de tentatives erronées, compte utilisateur bloqué')
            if e.response.text == '"USER_AUTHENTICATION_KO"':
                raise BrowserIncorrectPassword('Login ou mot de passe incorrect')
            raise

        self.session.headers.update({
            'authorization': "Bearer " + self.page.get_token(),
            'id': self.page.get_logged_user(),
        })

    @need_login
    def iter_accounts(self):
        return self.accounts_page.iter_accounts()

    @need_login
    def iter_history(self, account):
        logged_user = self.accounts_page.get_logged_user()
        accounts_params = self.accounts_page.get_accounts_params()
        self.periods.go(json={
            'loggedUser': logged_user,
            'possibleCardsToSee': accounts_params,
        })
        period_ids = self.page.get_periods()
        '''
        Each period corresponds to 1 month of history (dateFin and dateDebut are UNIX timestamps
        given in milliseconds)
        {
            "periodeId": 90,
            "dateDebut": 1625004000000,
            "dateFin": 1627509600000,
            "debitEntreprise": 3035.75,
            "creditEntreprise": 15.0,
            "debitPorteur": 0.0,
            "creditPorteur": 0.0,
            "debitTotal": 3035.75,
            "creditTotal": 15.0,
            "autre": 0.0
        }
        It seems that period which starting date are older than one year can't be retrieved anymore.
        In other words, we can only get 12 periods.
        '''
        for period_id in period_ids:
            json = {
                'cardId': account._card_id,
                'periodeId': period_id,
                'login': logged_user,
            }
            self.history.go(json=json)
            for tr in self.page.iter_history():
                yield tr

    @need_login
    def iter_coming(self, account):
        raise NotImplementedError()

    @need_login
    def iter_investment(self, account):
        raise NotImplementedError()
