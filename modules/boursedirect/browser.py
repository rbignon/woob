# -*- coding: utf-8 -*-

# Copyright(C) 2012-2020  Budget Insight
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

from woob.browser import URL, need_login, LoginBrowser
from woob.browser.exceptions import ClientError
from woob.exceptions import (
    BrowserIncorrectPassword, BrowserPasswordExpired, BrowserUnavailable, BrowserUserBanned,
)
from woob.tools.capabilities.bank.transactions import sorted_transactions
from woob.tools.decorators import retry

from .pages import (
    LoginPage, PasswordRenewalPage, AccountsPage, HistoryPage,
    InvestPage, MarketOrdersPage, MarketOrderDetailsPage,
    IsinPage, PortfolioPage, JsRedirectPage, HomePage,
)


class BoursedirectBrowser(LoginBrowser):
    BASEURL = 'https://www.boursedirect.fr'

    login = URL(r'/hub/auth/login', LoginPage)
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
    pre_invests = URL(r'/priv/new/portefeuille-TR.php\?nc=(?P<nc>\d+)')
    invests = URL(r'/streaming/compteTempsReelCK.php\?stream=0', InvestPage)
    market_orders = URL(r'/priv/new/ordres-en-carnet.php\?ong=7&nc=(?P<nc>\d+)', MarketOrdersPage)
    market_orders_details = URL(r'/priv/new/detailOrdre.php', MarketOrderDetailsPage)
    isin_page = URL(r'/fr/marche/', IsinPage)
    js_redirect = URL(r'/priv/fiche-valeur.php', JsRedirectPage)

    @retry(BrowserUnavailable, tries=2)
    def do_login(self):
        data = {
            'username': self.username,
            'password': self.password,
            'branding': 'boursedirect',
            'redirect': '',
        }
        try:
            self.login.go(json=data)
        except ClientError as e:
            if e.response.status_code == 401:
                login_page = LoginPage(self, e.response)
                error_message = login_page.get_error_message()
                if error_message in ('bad_credentials_error', 'error_bad_credentials'):
                    raise BrowserIncorrectPassword(
                        message='Couple login mot de passe incorrect',
                        bad_fields=['login'],
                    )
                elif error_message == 'error_password_not_found':
                    raise BrowserIncorrectPassword(
                        message='Couple login mot de passe incorrect',
                        bad_fields=['password'],
                    )
                elif error_message == 'error_locked_user':
                    raise BrowserUserBanned()
                elif error_message == 'error_expired_password':
                    raise BrowserPasswordExpired(
                        locale='fr-FR', message='Vous devez changer votre mot de passe depuis le site web.'
                    )
                raise AssertionError(f'Unhandled error during login: {error_message}')
            raise

    @need_login
    def iter_accounts(self):
        self.accounts.go()
        for account in self.page.iter_accounts():
            self.accounts.go(nc=account._select)
            self.page.fill_account(obj=account)
            yield account

    @need_login
    def iter_investment(self, account):
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
        if account.type in (account.TYPE_MARKET, account.TYPE_PEA):
            self.history.go(nc=account._select)
        else:
            raise NotImplementedError()
        return sorted_transactions(self.page.iter_history())
