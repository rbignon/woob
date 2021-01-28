# -*- coding: utf-8 -*-

# Copyright(C) 2012-2021  Budget Insight
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

from __future__ import unicode_literals

from weboob.capabilities.bank import Account, AccountNotFound
from weboob.capabilities.base import find_object
from weboob.browser import LoginBrowser, need_login, URL
from weboob.exceptions import BrowserIncorrectPassword, NoAccountsException, ActionNeeded

from .pages import (
    LoginPage, HomePage, HistoryPage, AccountPage, PocketPage, ErrorPage,
    InvestmentDetailPage, InvestmentPerformancePage, SituationPage,
)

class TransatplanBrowser(LoginBrowser):
    BASEURL = 'https://transatplan.banquetransatlantique.com'

    error = URL(r'.*', ErrorPage)
    login = URL(r'/fr/identification/authentification.html', LoginPage)
    situation = URL(r'/fr/client/votre-situation.aspx$', SituationPage)
    account = URL(r'/fr/client/votre-situation.aspx\?FID=GoOngletCompte',
                  r'/fr/client/votre-situation.aspx\?.*GoRetour.*',
                  r'/fr/client/votre-situation.aspx\?.*GoCourLst.*',
                  AccountPage)
    investment_detail = URL(r'/fr/client/votre-situation.aspx\?.*GoCourLst.*', InvestmentDetailPage)
    investment_performance = URL(r'/fr/client/VAL_FicheCours.aspx.*', InvestmentPerformancePage)
    pocket = URL(r'/fr/client/votre-situation.aspx\?.*GoSitOptLst.*', PocketPage)
    history = URL(r'/fr/client/votre-situation.aspx\?.*GoCptMvt.*', HistoryPage)
    home = URL(r'/fr/client/Accueil.aspx\?FID=GoSitAccueil.*', HomePage)

    def do_login(self):
        self.login.go()
        self.page.login(self.username, self.password)
        if self.login.is_here():
            raise BrowserIncorrectPassword(self.page.get_error())
        if self.situation.is_here():
            raise ActionNeeded(self.page.get_action_needed())
        assert self.page

    @need_login
    def iter_accounts(self):
        self.account.stay_or_go()

        if self.page.has_no_account():
            raise NoAccountsException()

        for account in self.page.iter_especes():
            yield account

        company_name = self.page.get_company_name()
        for account in self.page.iter_titres():
            account.company_name = company_name
            yield account

    @need_login
    def iter_history(self, account):
        account = find_object(self.iter_accounts(), id=account.id, error=AccountNotFound)

        # The website does not know what is a history
        if not account.url or account.type == Account.TYPE_MARKET:
            return []
        self.location(account.url)
        history = self.page.iter_history()
        self.do_return()
        return history

    @need_login
    def iter_investment(self, account):
        if account.type != Account.TYPE_MARKET:
            return

        account = find_object(self.iter_accounts(), id=account.id, error=AccountNotFound)
        investments = self.page.iter_investment()
        for inv in investments:
            if inv._performance_url:
                self.location(inv._performance_url)
                link = self.page.get_performance_link()
                if link:
                    self.location(link)
                    self.page.fill_investment(obj=inv)
            yield inv
        self.do_return()

    @need_login
    def iter_pocket(self, account):
        if account.type != Account.TYPE_MARKET:
            return

        account = find_object(self.iter_accounts(), id=account.id, error=AccountNotFound)
        self.location(account._url_pocket)
        pockets = self.page.iter_pocket()
        for pocket in pockets:
            yield pocket
        self.do_return()

    def do_return(self):
        if hasattr(self.page, 'do_return'):
            self.page.do_return()
