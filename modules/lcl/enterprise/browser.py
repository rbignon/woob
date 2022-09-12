# -*- coding: utf-8 -*-

# Copyright(C) 2016      Edouard Lambert
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

# flake8: compatible

import re

from woob.browser import LoginBrowser, URL, need_login
from woob.capabilities.bank.base import Account
from woob.exceptions import BrowserIncorrectPassword
from woob.capabilities.bank import AccountOwnerType

from .pages import (
    LoginPage, TooManySessionsPage, CardsPage, CardsMovementsPage,
    MovementsPage, ProfilePage, PassExpiredPage,
)


class LCLEnterpriseBrowser(LoginBrowser):
    BASEURL = 'https://entreprises.secure.lcl.fr'

    pass_expired = URL('/outil/IQEN/Authentication/forcerChangePassword', PassExpiredPage)
    login = URL(
        '/outil/IQEN/Authentication/indexRedirect',
        '/outil/IQEN/Authentication/(?P<page>.*)',
        LoginPage
    )

    # we can be redirected here during login if a session is already active.
    too_many_sessions = URL('/outil/IQEN/Authentication/dejaConnecte', TooManySessionsPage)

    cards = URL('/outil/IQRC/Accueil', CardsPage)
    cards_movements = URL(r'/outil/IQRC/Detail/detailCB\?index=(?P<index>.*)', CardsMovementsPage)
    movements = URL(
        '/outil/IQMT/mvt.Synthese/syntheseMouvementPerso',
        '/outil/IQMT/mvt.Synthese',
        MovementsPage
    )
    profile = URL('/outil/IQGA/FicheUtilisateur/maFicheUtilisateur', ProfilePage)

    def __init__(self, config, *args, **kwargs):
        super(LCLEnterpriseBrowser, self).__init__(*args, **kwargs)
        self.accounts = None
        self.owner_type = AccountOwnerType.ORGANIZATION

    def deinit(self):
        if self.page and self.page.logged:
            self.login.go(page="logout")
            self.login.go(page="logoutOk")
            assert self.login.is_here(page="logoutOk") or self.login.is_here(page="sessionExpiree")
        super(LCLEnterpriseBrowser, self).deinit()

    def do_login(self):
        self.login.go().login(self.username, self.password)

        if self.login.is_here():
            error = self.page.get_error()

            if error:
                raise BrowserIncorrectPassword(error)

    @need_login
    def get_accounts_list(self):
        if not self.accounts:
            self.accounts = list(self.movements.go().iter_accounts())

        for account in self.accounts:
            account.owner_type = self.owner_type
            yield account

        yield from self.iter_cards()

    @need_login
    def get_form_data(self, link):
        m = re.search(r"'(\d+).*'(\d+)", link)
        if m:
            return {
                'CBParentData': m.group(1),
                'CBEnfantData': m.group(2),
            }
        return None

    @need_login
    def iter_cards(self):
        self.cards.go()
        # We check if there are several companies that have cards
        companies = self.page.get_card_company_page_links()
        if companies:
            for company in companies:
                self.cards.go()
                self.page.go_to_card_company_page(self.get_form_data(company))
                yield from self.page.iter_cards(_company=company)

        else:
            yield from self.page.iter_cards(_company=None)

    @need_login
    def get_history(self, account):
        if account.type == Account.TYPE_CARD:
            return []

        if account._data:
            return self.open(account._url, data=account._data).page.iter_history()
        return self.movements.go().iter_history()

    @need_login
    def get_profile(self):
        return self.profile.go().get_profile()

    @need_login
    def get_coming(self, account):
        if account.type != Account.TYPE_CARD:
            return []
        # When there are many cards we must go to the page where the cards are listed
        # in order to get the right coming page for this card
        self.cards.go()
        if account._company_link:
            # Select the right company
            self.page.go_to_card_company_page(self.get_form_data(account._company_link))
        if account._num_page:
            # Go to the right page
            self.location('/outil/IQRC/Accueil/paginerListeCB', data={'numPage': account._num_page})

        self.cards_movements.go(index=account._index)
        return self.page.iter_coming()

    @need_login
    def get_investment(self, account):
        raise NotImplementedError()

    @need_login
    def iter_market_orders(self, account):
        raise NotImplementedError()


class LCLEspaceProBrowser(LCLEnterpriseBrowser):
    BASEURL = 'https://espacepro.secure.lcl.fr'
