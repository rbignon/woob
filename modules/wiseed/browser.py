# Copyright(C) 2019      Vincent A
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

from woob.browser import URL, LoginBrowser, StatesMixin, need_login
from woob.browser.exceptions import ClientError, HTTPNotFound
from woob.capabilities.bank import NoAccountsException
from woob.capabilities.captcha import RecaptchaV2Question
from woob.exceptions import BrowserIncorrectPassword

from .pages import InvestmentsPage, ProfilePage, WalletPage, WebsiteKeyPage


# TODO implement documents

class WiseedBrowser(LoginBrowser, StatesMixin):
    BASEURL = 'https://www.wiseed.com'

    home = URL(r'/$')
    login = URL(r'/api/auth/signin')
    key_js = URL(r'/client/RecaptchaForm\.(?P<recaptcha_form>\w*)\.js', WebsiteKeyPage)
    refresh = URL(r'/api/auth/refreshtoken')
    wallet = URL(r'/api/accounts/me/wallet', WalletPage)
    investments = URL(r'/api/accounts/me/investments', InvestmentsPage)
    profile = URL(r'/api/accounts/me', ProfilePage)

    def __init__(self, config, *args, **kwargs):
        self.config = config
        super(WiseedBrowser, self).__init__(config['login'].get(), config['password'].get(), *args, **kwargs)

    def do_login(self):
        if self.session.cookies.get('refresh_token'):
            # Since we don't know how many times the refresh is working, we refresh to avoid the captcha,
            # if /refresh returns an error, we go back to the captcha
            try:
                # Nothing to send, access and refresh are in the cookies, but it requires a post
                self.refresh.go(data='')
                return
            # The refresh token URI sometimes returns a 404 without any reason, so we except HTTPNotFound.
            except (ClientError, HTTPNotFound):
                pass

        request_payload = {
            'email': self.username,
            'password': self.password,
        }
        if self.config['captcha_response'].get() is not None:
            request_payload['g-recaptcha-response'] = self.config['captcha_response'].get()

            try:
                self.login.go(json=request_payload)
            except ClientError as e:
                response_body = e.response.json()
                error_message = response_body.get('message')

                if error_message == "Bad credentials":
                    raise BrowserIncorrectPassword()

                if not error_message:
                    error_field = response_body.get('fieldErrors', [{}])[0].get('field')
                    if error_field == 'email':
                        raise BrowserIncorrectPassword(bad_fields=['login'])
                    raise AssertionError(f'Unhandled error field at login : {error_field}')
                raise AssertionError(f'Unhandled error at login : {error_message}')
        else:
            # Did not encountered login without captcha, but we try it anyway.
            # If we see that captcha is systematic then remove this part.
            try:
                # if this request return a 200 (not tested) then we assume that access_token and refresh are set
                # in the cookies and then continue
                self.login.go(json=request_payload)
                return
            except ClientError:
                # Since login without captcha hasn't been tested, we must skip this request and go for captcha instead.
                pass

            # website_key can be found in javascript, don't know what happen if website is not requiring a captcha
            # to change.
            website_key = self.get_website_key()
            website_url = self.BASEURL
            raise RecaptchaV2Question(website_key=website_key, website_url=website_url)

    def get_website_key(self):
        # We must do the whole journey from the home page to get .js numbers and obtain the website key.
        # These numbers seem to change once a day
        self.home.go()
        recaptcha_form = re.search(
            rf'{self.key_js.urls[0]}',
            self.response.headers['link']
        ).group('recaptcha_form')
        self.key_js.go(recaptcha_form=recaptcha_form)
        return self.page.get_website_key()

    @need_login
    def iter_accounts(self):
        self.profile.go()

        # On freshly created accounts, request on /wallet return 404 if there is no wallet created.
        if not self.page.get_wallet_status():
            raise NoAccountsException()

        account = self.page.get_account()

        # There is a /stats route returning a "valuation" but the value isn't the one expected;
        # Indeed the value is the sum of all the money ever invested on this account.
        account.balance = sum(inv.valuation for inv in self.iter_investment())
        yield account

    @need_login
    def iter_investment(self):
        self.wallet.go()
        yield self.page.get_liquidities()

        self.investments.go()

        invest_types = {
            'actions': self.page.iter_stocks(),
            'obligations': self.page.iter_bonds(),
            'titresParticipatifs': self.page.iter_equities(),
        }
        for invest_type, iter_invest in invest_types.items():
            if self.page.get_invest_list(invest_type):
                for inv in iter_invest:
                    yield inv

    @need_login
    def get_profile(self):
        self.profile.go()
        return self.page.get_profile()
