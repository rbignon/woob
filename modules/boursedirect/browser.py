# -*- coding: utf-8 -*-

# Copyright(C) 2012-2020  Budget Insight
#
# This file is part of a weboob module.
#
# This weboob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This weboob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this weboob module. If not, see <http://www.gnu.org/licenses/>.

# flake8: compatible

from __future__ import unicode_literals

from weboob.browser import URL, need_login, LoginBrowser
from weboob.exceptions import BrowserUnavailable, BrowserPasswordExpired
from weboob.tools.capabilities.bank.transactions import sorted_transactions
from weboob.tools.decorators import retry

from .pages import (
    LoginPage, PasswordRenewalPage, AccountsPage, HistoryPage,
    InvestPage, MarketOrdersPage, MarketOrderDetailsPage,
    LifeInsurancePage, IsinPage, PortfolioPage, JsRedirectPage,
    HomePage,
)


class BoursedirectBrowser(LoginBrowser):
    BASEURL = 'https://www.boursedirect.fr'

    login = URL(r'/fr/login', LoginPage)
    password_renewal = URL(r'/fr/changer-mon-mot-de-passe', PasswordRenewalPage)
    home = URL(r'/fr/page/inventaire', HomePage)
    accounts = URL(
        r'/priv/new/compte.php$',
        r'/priv/new/compte.php\?nc=(?P<nc>\d+)',
        r'/priv/listeContrats.php\?nc=(?P<nc>\d+)',
        AccountsPage
    )
    history = URL(r'/priv/new/historique-de-compte.php\?ong=3&nc=(?P<nc>\d+)', HistoryPage)
    portfolio = URL(r'/fr/page/portefeuille', PortfolioPage)
    pre_invests = URL(r'/priv/portefeuille-TR.php\?nc=(?P<nc>\d+)')
    invests = URL(r'/streaming/compteTempsReelCK.php\?stream=0', InvestPage)
    market_orders = URL(r'/priv/new/ordres-en-carnet.php\?ong=7&nc=(?P<nc>\d+)', MarketOrdersPage)
    market_orders_details = URL(r'/priv/new/detailOrdre.php', MarketOrderDetailsPage)
    lifeinsurance = URL(
        r'/priv/asVieSituationEncours.php',
        r'/priv/encours.php\?nc=\d+&idUnique=[\dA-F-]+',
        LifeInsurancePage
    )
    isin_page = URL(r'/fr/marche/', IsinPage)
    js_redirect = URL(r'/priv/fiche-valeur.php', JsRedirectPage)

    @retry(BrowserUnavailable)
    def do_login(self):
        self.login.go()
        self.page.do_login(self.username, self.password)
        if self.login.is_here():
            self.page.check_error()

        if self.password_renewal.is_here():
            # Customers must renew their password on the website
            raise BrowserPasswordExpired(self.page.get_message())

        # Sometimes the login fails for no apparent reason. The issue doesn't last so a retry should suffice.
        if not self.page.logged:
            raise BrowserUnavailable('We should be logged at this point')

    @need_login
    def iter_accounts(self):
        for account in self.iter_accounts_but_insurances():
            yield account

        self.lifeinsurance.go()
        if self.lifeinsurance.is_here() and self.page.has_account():
            yield self.page.get_account()

    def iter_accounts_but_insurances(self):
        self.accounts.go()
        for account in self.page.iter_accounts():
            self.accounts.go(nc=account._select)
            self.page.fill_account(obj=account)
            yield account

    @need_login
    def iter_investment(self, account):
        if account.type == account.TYPE_LIFE_INSURANCE:
            self.accounts.go()
            self.lifeinsurance.go()
            for inv in self.page.iter_investment():
                yield inv
        else:
            self.pre_invests.go(nc=account._select)
            self.invests.go()

            for inv in self.page.iter_investment():
                yield inv
            yield self.page.get_liquidity()

    @need_login
    def iter_market_orders(self, account):
        if account.type not in (account.TYPE_PEA, account.TYPE_MARKET):
            return

        self.market_orders.go(nc=account._select)
        for order in self.page.iter_market_orders():
            if order.url:
                self.location(order.url)
                if self.market_orders_details.is_here():
                    self.page.fill_market_order(obj=order)
                else:
                    self.logger.warning('Unknown details URL for market order %s.', order.label)
            else:
                self.logger.warning('Market order %s has no details URL.', order.label)
            yield order

    @need_login
    def iter_history(self, account):
        if account.type == account.TYPE_LIFE_INSURANCE:
            self.lifeinsurance.go()
        elif account.type in (account.TYPE_MARKET, account.TYPE_PEA):
            self.history.go(nc=account._select)
        else:
            raise NotImplementedError()
        return sorted_transactions(self.page.iter_history())
