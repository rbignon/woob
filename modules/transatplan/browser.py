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

# flake8: compatible

from __future__ import unicode_literals

from woob.capabilities.bank import Account
from woob.browser import LoginBrowser, need_login, URL
from woob.exceptions import BrowserIncorrectPassword, NoAccountsException, ActionNeeded

from .pages import (
    LoginPage, HomePage, HistoryPage, AccountPage, ErrorPage,
    InvestmentDetailPage, InvestmentPerformancePage, SituationPage,
    PocketsPage, PocketDetailPage, ActionNeededPage,
)


class TransatplanBrowser(LoginBrowser):
    BASEURL = 'https://transatplan.banquetransatlantique.com'

    error = URL(r'.*', ErrorPage)
    login = URL(r'/fr/identification/authentification.html', LoginPage)
    action_needed = URL(r'/fr/client/votre-situation.aspx\?FID=GoOngletCompte', ActionNeededPage)
    situation = URL(r'/fr/client/votre-situation.aspx$', SituationPage)
    account = URL(
        r'/fr/client/votre-situation.aspx\?FID=GoOngletCompte',
        r'/fr/client/votre-situation.aspx\?.*GoRetour.*',
        r'/fr/client/votre-situation.aspx\?.*GoCourLst.*',
        AccountPage
    )
    investment_detail = URL(r'/fr/client/votre-situation.aspx\?.*GoCourLst.*', InvestmentDetailPage)
    investment_performance = URL(r'/fr/client/VAL_FicheCours.aspx.*', InvestmentPerformancePage)
    pockets = URL(r'/fr/client/votre-situation.aspx\?FID=GoSituation', PocketsPage)
    history = URL(r'/fr/client/votre-situation.aspx\?_productfilter=.*GoCptMvt.*', HistoryPage)
    pocket_details = URL(r'/fr/client/votre-situation.aspx\?_productfilter=', PocketDetailPage)
    home = URL(r'/fr/client/Accueil.aspx\?FID=GoSitAccueil.*', HomePage)

    def do_login(self):
        self.login.go()
        self.page.login(self.username, self.password)
        if self.login.is_here():
            raise BrowserIncorrectPassword(self.page.get_error())
        if self.situation.is_here() or self.action_needed.is_here():
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

        self.account.go()
        investments = self.page.iter_investment()
        for inv in investments:
            if inv._performance_url:
                self.location(inv._performance_url)
                link = self.page.get_performance_link()
                self.page.fill_investment(obj=inv)
                if link:
                    self.location(link)
                    self.page.fill_investment(obj=inv)
            yield inv

        self.do_return()

    @need_login
    def iter_pocket(self, account):
        if account.type != Account.TYPE_MARKET:
            return []

        pocket_list = list()
        for inv in self.iter_investment(account):
            self.pockets.go()
            for pocket in self.page.iter_pocket(inv=inv):
                # we need to retrieve the underlying invest/stock for each pocket.
                # then we can check if the pocket is related to the same invest/stock.
                # if details_url is missing, we ignore the pocket.
                if pocket._details_url:
                    self.location(pocket._details_url)
                    underlying_invest = self.page.get_underlying_invest()
                    if underlying_invest not in inv.label.lower():
                        continue
                    pocket_list.append(pocket)

        return pocket_list

    def do_return(self):
        if hasattr(self.page, 'do_return'):
            self.page.do_return()
