# -*- coding: utf-8 -*-

# Copyright(C) 2013      Romain Bignon
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

from urllib3.exceptions import ReadTimeoutError

from weboob.tools.decorators import retry
from weboob.browser import LoginBrowser, URL, need_login
from weboob.exceptions import BrowserIncorrectPassword, BrowserUnavailable
from weboob.browser.exceptions import ClientError

from .pages import (
    LoginPage, WrongpassPage, HomePage, AccountsPage,
    InvestmentPage, HistoryPage, InfoPage,
)

__all__ = ['ApivieBrowser']


class ApivieBrowser(LoginBrowser):
    login = URL(
        r'/$',
        r'/accueil$',
        r'/perte.*',
        LoginPage
    )
    wrongpass = URL(r'/accueil.*saveLastPath=false', WrongpassPage)
    info = URL(r'/(coordonnees|accueil-connect)', InfoPage)
    home = URL(r'/contrats-cosy3', HomePage)
    accounts = URL(r'https://(?P<api_url>.*)/interne/contrat/', AccountsPage)
    investments = URL(r'https://(?P<api_url>.*)/contrat/(?P<account_id>\d+)$', InvestmentPage)
    history = URL(r'https://(?P<api_url>.*)/contrat/(?P<account_id>\d+)/mouvements', HistoryPage)

    def __init__(self, website, *args, **kwargs):
        super(ApivieBrowser, self).__init__(*args, **kwargs)
        self.BASEURL = 'https://%s' % website
        self.APIURL = 'hub.apivie.fr'
        self.client_number = ''

    def do_login(self):
        if not self.login.is_here():
            self.location('/accueil')

        self.page.login(self.username, self.password)

        if self.wrongpass.is_here():
            raise BrowserIncorrectPassword()

    # Accounts, Investments & Transactions are scraped on the Apivie API (https://hub.apivie.fr).
    # The API is unstable and we get various errors, hence the @retry decorators.

    @need_login
    @retry(BrowserUnavailable, tries=3)
    def iter_accounts(self):
        self.accounts.go(api_url=self.APIURL)
        return self.page.iter_accounts()

    @need_login
    @retry(BrowserUnavailable, tries=3)
    def iter_investment(self, account):
        try:
            self.investments.go(api_url=self.APIURL, account_id=account.id)
        except (ReadTimeoutError, ClientError) as e:
            self.logger.warning('Error when trying to access account investments: %s', e)
            raise BrowserUnavailable()

        return self.page.iter_investments()

    @need_login
    @retry(BrowserUnavailable, tries=3)
    def iter_history(self, account):
        try:
            self.history.go(api_url=self.APIURL, account_id=account.id)
        except (ReadTimeoutError, ClientError) as e:
            self.logger.warning('Error when trying to access account history: %s', e)
            raise BrowserUnavailable()

        return self.page.iter_history()

    def get_subscription_list(self):
        raise NotImplementedError()

    def iter_documents(self, subscription):
        raise NotImplementedError()

    def download_document(self, document):
        raise NotImplementedError()
