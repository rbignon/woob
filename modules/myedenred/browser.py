# -*- coding: utf-8 -*-

# Copyright(C) 2017      Théo Dorée
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

from functools import wraps

from weboob.browser import URL, OAuth2PKCEMixin, PagesBrowser
from weboob.exceptions import BrowserIncorrectPassword, NocaptchaQuestion, WrongCaptchaResponse
from weboob.browser.exceptions import ServerError, ClientError

from .pages import LoginPage, AccountsPage, TransactionsPage, JsParamsPage, JsUserPage, HomePage


def need_login(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.logged:
            self.do_login()
        return func(self, *args, **kwargs)

    return wrapper


class MyedenredBrowser(OAuth2PKCEMixin, PagesBrowser):
    BASEURL = 'https://app-container.eu.edenred.io'

    AUTHORIZATION_URI = 'https://sso.eu.edenred.io/connect/authorize'
    ACCESS_TOKEN_URI = 'https://sso.eu.edenred.io/connect/token'

    redirect_uri = 'https://www.myedenred.fr/connect'

    home = URL(r'https://myedenred.fr/$', HomePage)
    login = URL(r'https://sso.eu.edenred.io/login', LoginPage)
    accounts = URL(r'/v1/users/(?P<username>.+)/cards', AccountsPage)
    transactions = URL(
        r'/v1/users/(?P<username>.+)/accounts/(?P<card_class>.*)-(?P<account_ref>\d+)/operations',
        TransactionsPage,
    )
    params_js = URL(r'https://www.myedenred.fr/js/parameters.(?P<random_str>\w+).js', JsParamsPage)
    connexion_js = URL(r'https://myedenred.fr/js/connexion.(?P<random_str>\w+).js', JsUserPage)

    def __init__(self, config, *args, **kwargs):
        super(MyedenredBrowser, self).__init__(*args, **kwargs)

        self.username = config['login'].get()
        self.password = config['password'].get()
        self.config = config

        self._fetch_auth_parameters()

    def _fetch_auth_parameters(self):
        self.home.go()
        params_random_str = self.page.get_href_randomstring('parameters')
        connexion_random_str = self.page.get_href_randomstring('connexion')

        self.params_js.go(random_str=params_random_str)
        js_parameters = self.page.get_json_content()

        self.connexion_js.go(random_str=connexion_random_str)
        connexion_js = self.page.get_json_content()

        self.client_id = js_parameters['EDCId']
        self.client_secret = js_parameters['EDCSecret']
        self.x_client_id = js_parameters['ClientId']
        self.x_client_secret = js_parameters['ClientSecret']
        self.nonce = connexion_js['nonce']
        self.response_type = connexion_js['response_type']
        self.SCOPE = connexion_js['scope']
        self.ui_locales = connexion_js['ui_locales']
        self.code_challenge_method = connexion_js['code_challenge_method']

    def build_authorization_parameters(self):
        params = {
            'acr_values': 'tenant:fr-ben',
            'client_id': self.client_id,
            'code_challenge': self.pkce_challenge,
            'code_challenge_method': self.code_challenge_method,
            'nonce': self.nonce,
            'redirect_uri': self.redirect_uri,
            'response_type': self.response_type,
            'scope': self.SCOPE,
            'state': '',
            'ui_locales': self.ui_locales,
        }
        return params

    def request_authorization(self):
        self.session.cookies.clear()

        self.location(self.build_authorization_uri())
        website_key = self.page.get_recaptcha_site_key()

        if not self.config['captcha_response'].get() and website_key:
            raise NocaptchaQuestion(website_key=website_key, website_url=self.url)

        form = self.page.get_login_form()
        form['Username'] = self.username
        form['Password'] = self.password
        form['g-recaptcha-response'] = self.config['captcha_response'].get()
        form.submit()

        if self.login.is_here():
            message = self.page.get_error_message()
            if 'Couple Email' in message:
                raise BrowserIncorrectPassword()
            elif 'validation du captcha' in message:
                raise WrongCaptchaResponse()
            raise AssertionError('Unhandled error at login: "%s".' % message)

        self.auth_uri = self.url
        self.request_access_token(self.auth_uri)

    def build_access_token_parameters(self, values):
        return {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code': values['code'],
            'code_verifier': self.pkce_verifier,
            'grant_type': 'authorization_code',
            'redirect_uri': self.redirect_uri,
        }

    def do_token_request(self, data):
        return self.open(self.ACCESS_TOKEN_URI, data=data, headers={'X-request-id': 'token'})

    def use_refresh_token(self):
        data = self.build_refresh_token_parameters()

        try:
            auth_response = self.do_token_request(data).json()
        except ClientError as e:
            self.refresh_token = None
            self.auth_uri = None
            # The refresh token expires at ~24h. Repeat the login procedure from the beginning
            if e.response.status_code in [400, 401]:
                self.request_authorization()
            else:
                raise e
        else:
            self.update_token(auth_response)

    def build_request(self, *args, **kwargs):
        headers = kwargs.setdefault('headers', {})
        super(OAuth2PKCEMixin, self).build_request(*args, **kwargs)
        if self.access_token:
            headers['X-Client-Id'] = self.x_client_id
            headers['X-Client-Secret'] = self.x_client_secret
            headers['X-request-id'] = 'edg_call'
        return super(MyedenredBrowser, self).build_request(*args, **kwargs)

    @need_login
    def iter_accounts(self):
        self.accounts.go(username=self.username)
        return self.page.iter_accounts()

    @need_login
    def iter_history(self, account):
        page_index = 0
        # Max value, allowed by the webiste, for page_size is 50
        # Note it may crash for some requests (it seems for client with a few transactions)
        page_size = 50
        nb_transactions = page_size
        fetched_transactions = 0

        while nb_transactions == page_size:
            try:
                self.transactions.go(
                    username=self.username,
                    card_class=account._card_class,
                    account_ref=account._account_ref,
                    params={
                        'page_index': page_index,
                        'page_size': page_size,
                    }
                )
            except ServerError as e:
                # If page size is too much high the server may answer with a strange 500 containing a success json:
                # '{"meta": {"status": "failed", "messages": [{"code": 200, "level": "info", "text": "OK"}]}}'
                # We do not try to decode it to keep it simple and check its content as string
                if not (
                    e.response.status_code == 500
                    and b"200" in e.response.content
                    and b"OK" in e.response.content
                ):
                    # Not an exception because of our pagination
                    raise

                if page_size <= 2:
                    if not fetched_transactions:
                        # we were unable to fetch any transaction
                        # it does not look like a page size related problem
                        raise
                    else:
                        # now we get 500 but we have fetched transactions,
                        # so we consider we have reached the server limit
                        break

                # limit items per page and try again
                page_index *= 5
                page_size //= 5
                nb_transactions = page_size
                self.logger.info(
                    "Limiting items per page to %s because of a server crash: %r",
                    page_size,
                    e,
                )
                continue

            nb_transactions = len(self.page.doc['data'])
            for tr in self.page.iter_transactions():
                fetched_transactions += 1
                yield tr

            page_index += 1
