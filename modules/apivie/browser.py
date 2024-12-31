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

from time import time

import jwt
from urllib3.exceptions import ReadTimeoutError

from woob.browser.browsers import need_login
from woob.browser.exceptions import ClientError
from woob.browser.mfa import TwoFactorBrowser
from woob.browser.url import URL
from woob.exceptions import BrowserIncorrectPassword, BrowserUnavailable, OTPSentType, SentOTPQuestion
from woob.tools.decorators import retry

from .pages import AccountsPage, HistoryPage, HomePage, InfoPage, InvestmentPage, LoginPage


__all__ = ['ApivieBrowser']


class ApivieBrowser(TwoFactorBrowser):
    login = URL(r'/auth', LoginPage)
    info = URL(r'/(coordonnees|accueil-connect)', InfoPage)
    home = URL(r'/contrats-cosy3', HomePage)
    accounts = URL(r'https://(?P<api_url>.*)/interne/contrats/', AccountsPage)
    investments = URL(r'https://(?P<api_url>.*)/contrat/(?P<account_id>\d+)$', InvestmentPage)
    history = URL(r'https://(?P<api_url>.*)/contrat/(?P<account_id>\d+)/mouvements', HistoryPage)

    __states__ = ('access_token',)

    TIMEOUT = 40

    def __init__(self, config, website, *args, **kwargs):
        self.config = config
        super().__init__(self.config, *args, **kwargs)
        self.BASEURL = 'https://%s' % website
        self.APIURL = 'hub.apivie.fr'
        self.client_number = ''
        self.access_token = None
        self.AUTHENTICATION_METHODS = {
            'otp_sms': self.handle_sms,
        }

    def generate_jwt(self):
        # We can find this key in the js. As this js url is not
        # consistent in time, it's easier to hardcode the key
        signature_key = '742484ee0f879d89ebb57a96c898d53006833bbf7043d64f2b090b3a90eb28efff841f00aeeb2991ac3f125448b7f73dce4923071aff9b31c0026891256ce416'
        jwt_token = jwt.encode(
            {'iat': time(), 'sub': self.username},
            signature_key
        )
        # If the version of pyjwt is >2.0.0, jwt.encode returns a bytes string otherwise a simple string.
        if isinstance(jwt_token, bytes):
            return jwt_token.decode()
        return jwt_token

    def locate_browser(self, state):
        pass

    @property
    def logged(self):
        # We need to use verify and verify signature, this is not blocking
        # and allows to be compatible with pyjwt versions above 2.0.0 and below
        if (
            self.access_token
            and jwt.decode(self.access_token, options={'verify_signature': False}, verify=False)['exp'] > time()
        ):
            self.session.headers['Authorization'] = f'Bearer {self.access_token}'
            return True
        return False

    def init_login(self):
        # according to APICIL support sms validation is now systematic, so if there are no
        # access_token or if the access_token is not valid we check if we are interactive
        data = {
            'jeton': self.generate_jwt(),
            'username': self.username,
            'password': self.password,
        }
        try:
            self.login.go(json=data)
        except ClientError as e:
            if e.response.status_code == 400:
                error_message = LoginPage(self, e.response).get_error_message()
                if 'Jeton CSRF invalide' in error_message:
                    self.logger.warning('The actual signature key is probably no longer valid')
                    raise
                if 'incorrect' in error_message:
                    raise BrowserIncorrectPassword()
                if 'Code de sécurité à saisir' in error_message:
                    # If we are here, the SMS has already been sent to the user.
                    raise SentOTPQuestion(
                        'otp_sms',
                        medium_type=OTPSentType.SMS,
                        message=error_message,
                    )
            raise
        self.access_token = self.page.get_access_token()
        self.session.headers['Authorization'] = f'Bearer {self.access_token}'
        # Accounts, Investments & Transactions are scraped on the Apivie API (https://hub.apivie.fr).
        # The API is unstable and we get various errors, hence the @retry decorators.

    def handle_sms(self):
        data = {
            'jeton': self.generate_jwt(),
            'username': self.username,
            'password': self.password,
            'otp': self.otp_sms,
        }
        try:
            self.login.go(json=data)
        except ClientError as e:
            error_message = LoginPage(self, e.response).get_error_message()
            if 'veuillez vérifier votre saisie.' in error_message:
                raise BrowserIncorrectPassword(error_message)
            raise
        self.access_token = self.page.get_access_token()
        self.session.headers['Authorization'] = f'Bearer {self.access_token}'

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
