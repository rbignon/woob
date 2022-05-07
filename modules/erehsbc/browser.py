# -*- coding: utf-8 -*-

# Copyright(C) 2016      Edouard Lambert
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

from base64 import b64decode, b64encode
from random import choices
from string import digits
from urllib.parse import parse_qsl, urlparse

try:
    from Cryptodome.Cipher import PKCS1_v1_5
    from Cryptodome.PublicKey import RSA
except ImportError:
    from Crypto.Cipher import PKCS1_v1_5
    from Crypto.PublicKey import RSA

from woob.browser import AbstractBrowser, URL
from woob.browser.exceptions import ClientError
from woob.exceptions import (
    BrowserIncorrectPassword, BrowserPasswordExpired,
    NeedInteractiveFor2FA, OTPSentType, SentOTPQuestion,
)

from .pages import AuthenticationPage, LoginPage, HomePage


class ErehsbcBrowser(AbstractBrowser):
    PARENT = 's2e'
    PARENT_ATTR = 'package.browser.ErehsbcBrowser'

    home_page = URL(r'/portal/salarie-hsbc/$', HomePage)
    login_page = URL(r'/portal/salarie-hsbc/connect', LoginPage)
    authentication_page = URL(
        r'https://iam.epargne-salariale-retraite.hsbc.fr/connect/json/authenticate\?realm=/hsbc_ws',
        AuthenticationPage
    )
    user_connect_page = URL(
        r'https://iam.epargne-salariale-retraite.hsbc.fr/connect/json/users\?_action=idFromSession&realm=/hsbc_ws'
    )

    __states__ = ('otp_json',)

    def __init__(self, config, *args, **kwargs):
        self.config = config
        self.otp_json = None
        kwargs['username'] = self.config['login'].get()
        kwargs['password'] = self.config['password'].get()
        super(ErehsbcBrowser, self).__init__(config, *args, **kwargs)

    # Parent is popping the URL from the state but we need it
    def dump_state(self):
        state = super(ErehsbcBrowser, self).dump_state()
        if hasattr(self, 'page') and self.page:
            state['url'] = self.page.url
        return state

    # Override parent or we get a LoggedOut exception during next connection
    def deinit(self):
        self.session.close()

    def do_login(self):
        # Each time we login, if we're not a trusted device registered
        # on the user profile, OTP is sent on the user email
        if self.config['otp'].get():
            self.otp_json['callbacks'][1]['input'][0]['value'] = self.config['otp'].get()

            try:
                self.authentication_page.go(json=self.otp_json)
                data = self.response.json()
                # If OTP is wrong, we can spot it thanks to website
                # response being otp_json again
                if data.get('callbacks'):
                    raise BrowserIncorrectPassword(bad_fields=['otp'])
            except ClientError as e:
                if e.response.status_code == 401:
                    raise BrowserPasswordExpired('Code de sécurité expiré')
                raise

            # In a regular browser, the JSON response is always about some devices selection.
            # That JSON is then posted with some updated values to finally get a tokenId as a response.
            # Browsing through woob makes the JSON response be directly the tokenId we're looking for.
            # Haven't seen it via woob yet but if ever the response is the device selection one, we make
            # sure to avoid adding any trusted device to the user profile
            if not data.get('tokenId'):
                data['callbacks'][0]['input'][0]['value'] = '1'
                self.authentication_page.go(json=data)

            # tokenId allows us to access user_connect_page which itself gives us the final login URL
            self.session.cookies['idtksam'] = data['tokenId']

            self.user_connect_page.go(data='')
            data = self.response.json()
            self.location(data['fullLoginURL'])

            full_login_url = dict(parse_qsl(urlparse(self.url).fragment))['goto']
            url_params = dict(parse_qsl(urlparse(full_login_url).query))

            data = {
                'redirect_uri': url_params['redirect_uri'],
                'scope': url_params['scope'],
                'state': url_params['state'],
                'nonce': url_params['nonce'],
                'response_type': url_params['response_type'],
                'client_id': url_params['client_id'],
                'csrf': self.session.cookies['idtksam'],
                'decision': 'allow',
            }

            self.location(full_login_url, data=data)

        else:
            # Most of the time, login process is done by posting on the same URL
            # different JSON callbacks that we may have to update with some values
            self.login_page.go()

            redirect_uri = dict(parse_qsl(urlparse(self.url).fragment))['goto']

            params = {
                'realm': '/hsbc_ws',
                'locale': 'fr',
                'service': 'authn_hsbc_ws',
                'goto': redirect_uri,
                'authIndexType': 'service',
                'authIndexValue': 'authn_hsbc_ws',
            }

            self.authentication_page.go(data='', params=params)

            # If needed, logic behind password encryption found in
            # '/connect/XUI/themes/authn_hsbc_ws/js/jsencrypt.js?_=1650371144583' and
            # '/connect/XUI/themes/authn_hsbc_ws/templates/openam/authn/DecryptPwdAndTokenReapp2.html?v=13.0.0-7'
            data = self.page.get_password_json()

            public_key = self.page.get_public_key()
            b64_public_key = b64decode(public_key)

            randomized_password = (''.join(choices(digits, k=24)) + self.password).encode()

            recipient_key = RSA.import_key(b64_public_key)
            cipher_rsa = PKCS1_v1_5.new(recipient_key)  # PKCS1_v1_5 needed to match JSEncrypt.encrypt() method
            encrypted_password = b64encode(cipher_rsa.encrypt(randomized_password))

            data['callbacks'][0]['input'][0]['value'] = self.username
            data['callbacks'][1]['input'][0]['value'] = encrypted_password
            data['callbacks'][2]['input'][0]['value'] = public_key

            # Only way to detect wrong credentials is through a 401 messageless error
            try:
                self.authentication_page.go(json=data)
            except ClientError as e:
                if e.response.status_code == 401:
                    raise BrowserIncorrectPassword()
                raise

            self.authentication_page.go(json=self.response.json())
            data = self.page.get_pre_otp_json()

            if self.page.is_pre_otp_here():
                if not self.is_interactive:
                    raise NeedInteractiveFor2FA()
                self.authentication_page.go(json=data)  # OTP sent to user here
                self.otp_json = self.page.get_otp_json()
                if self.otp_json['callbacks'][1]['output'][0]['value'] == 'Enter the received code':
                    raise SentOTPQuestion(
                        'otp',
                        medium_type=OTPSentType.EMAIL,
                        message='Entrez le code de sécurité'
                    )
            raise AssertionError('Unhandled authentication flow')
