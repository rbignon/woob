# -*- coding: utf-8 -*-

# Copyright(C) 2013      Romain Bignon
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

from urllib3.exceptions import ReadTimeoutError

from woob.tools.decorators import retry
from woob.browser.browsers import need_login
from woob.browser.url import URL
from woob.exceptions import (
    BrowserIncorrectPassword, BrowserUnavailable, AuthMethodNotImplemented,
)
from woob.browser.exceptions import ClientError
from woob.browser.mfa import TwoFactorBrowser

from .pages import (
    HomePage, AccountsPage,
    InvestmentPage, HistoryPage, InfoPage, LoginPage,
)

__all__ = ['ApivieBrowser']


class ApivieBrowser(TwoFactorBrowser):
    login = URL(r'/auth', LoginPage)
    info = URL(r'/(coordonnees|accueil-connect)', InfoPage)
    home = URL(r'/contrats-cosy3', HomePage)
    accounts = URL(r'https://(?P<api_url>.*)/interne/contrats/', AccountsPage)
    investments = URL(r'https://(?P<api_url>.*)/contrat/(?P<account_id>\d+)$', InvestmentPage)
    history = URL(r'https://(?P<api_url>.*)/contrat/(?P<account_id>\d+)/mouvements', HistoryPage)

    def __init__(self, config, website, *args, **kwargs):
        self.config = config
        super().__init__(self.config, *args, **kwargs)
        self.BASEURL = 'https://%s' % website
        self.APIURL = 'hub.apivie.fr'
        self.client_number = ''
        self.AUTHENTICATION_METHODS = {
            'otp_sms': self.handle_sms,
        }

    def init_login(self):
        data = {
            'username': self.username,
            'password': self.password,
        }
        try:
            self.login.go(json=data)
        except ClientError as e:
            if e.response.status_code == 400:
                error_message = LoginPage(self, e.response).get_error_message()
                if 'incorrect' in error_message:
                    raise BrowserIncorrectPassword()
                if 'Code de sécurité à saisir' in error_message:
                    raise AuthMethodNotImplemented(error_message)
                raise AssertionError(f'Unhandled error at login: {error_message}')
            raise

        self.session.headers['Authorization'] = 'Bearer ' + self.page.get_access_token()

    # Accounts, Investments & Transactions are scraped on the Apivie API (https://hub.apivie.fr).
    # The API is unstable and we get various errors, hence the @retry decorators.

    def handle_sms(self):
        # TODO implement the SCA
        pass

    @need_login
    @retry(BrowserUnavailable, tries=3)
    def iter_accounts(self):
        self.accounts.go(api_url=self.APIURL)
        for account in self.page.iter_accounts():
            try:
                self.investments.go(api_url=self.APIURL, account_id=account.id)
            except (ReadTimeoutError, ClientError) as e:
                self.logger.warning('Error when trying to access account details: %s', e)
                pass
            else:
                account.opening_date = self.page.get_opening_date()
            yield account

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
