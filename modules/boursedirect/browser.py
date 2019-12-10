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

from __future__ import unicode_literals

from weboob.browser import URL, need_login, LoginBrowser
from weboob.exceptions import BrowserUnavailable
from weboob.tools.capabilities.bank.transactions import sorted_transactions
from weboob.tools.decorators import retry

from .pages import (
    LoginPage, AccountsPage, HistoryPage, InvestPage, LifeInsurancePage, IsinPage,
)


class BoursedirectBrowser(LoginBrowser):
    BASEURL = 'https://www.boursedirect.fr'

    login = URL(r'/fr/login', LoginPage)
    accounts = URL(
        r'/priv/compte.php$',
        r'/priv/compte.php\?nc=(?P<nc>\d+)',
        AccountsPage
    )
    history = URL(r'/priv/compte.php\?ong=3&nc=(?P<nc>\d+)', HistoryPage)
    pre_invests = URL(r'/priv/portefeuille-TR.php\?nc=(?P<nc>\d+)')
    invests = URL(r'/streaming/compteTempsReelCK.php\?stream=0', InvestPage)
    lifeinsurance = URL(
        r'/priv/asVieSituationEncours.php',
        r'/priv/encours.php\?nc=\d+&idUnique=[\dA-F-]+',
        LifeInsurancePage
    )
    isin_page = URL(r'/fr/marche/', IsinPage)

    @retry(BrowserUnavailable)
    def do_login(self):
        self.login.go()
        self.page.do_login(self.username, self.password)
        if self.login.is_here():
            self.page.check_error()

        # Sometimes the login fails for no apparent reason. The issue doesn't last so a retry should suffice.
        if not self.page.logged:
            raise BrowserUnavailable('We should be logged at this point')

    @need_login
    def iter_accounts(self):
        self.accounts.go()
        for account in self.page.iter_accounts():
            self.accounts.go(nc=account._select)
            self.page.fill_account(obj=account)
            yield account

        self.lifeinsurance.go()
        if self.page.has_account():
            yield self.page.get_account()

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
    def iter_history(self, account):
        if account.type == account.TYPE_LIFE_INSURANCE:
            self.lifeinsurance.go()
        elif account.type in (account.TYPE_MARKET, account.TYPE_PEA):
            self.history.go(nc=account._select)
        else:
            raise NotImplementedError()
        return sorted_transactions(self.page.iter_history())
