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
try:
    from Cryptodome.Cipher import PKCS1_v1_5
    from Cryptodome.PublicKey import RSA
except ImportError:
    from Crypto.Cipher import PKCS1_v1_5
    from Crypto.PublicKey import RSA

from woob.browser import URL
from woob.browser.exceptions import ClientError
from woob.exceptions import (
    BrowserIncorrectPassword, BrowserPasswordExpired,
    NeedInteractiveFor2FA, OTPSentType, SentOTPQuestion,
)
from woob.tools.url import get_url_param
from woob_modules.s2e.browser import S2eBrowser

from .pages import AuthenticationPage, LoginPage


class ErehsbcBrowser(S2eBrowser):
    BASEURL = 'https://epargnant.ere.hsbc.fr'
    SLUG = 'hsbc'
    LANG = 'fr'  # ['fr', 'en']

    login_page = URL(r'/portal/salarie-(?P<slug>\w+)/connect', LoginPage)
    authentication_page = URL(
        r'https://iam.epargne-salariale-retraite.hsbc.fr/connect/json/authenticate\?realm=/hsbc_ws',
        AuthenticationPage
    )

    def __init__(self, config, *args, **kwargs):
        self.config = config
        self.otp_json = None
        self.redirect_uri = None
        self.__states__ += ('otp_json', 'redirect_uri')
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
        # There are two possible cases:
        # - we are not a trusted device registered and OTP will be sent on the user email
        # - we are a trusted device and we can connect directly without OTP
        if self.config['otp'].get() and self.otp_json:
            self.handle_otp()
        else:
            data = self.init_login()
            if '/connect/console' not in data.get('successUrl', ''):
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
                            medium_label=self.page.get_email(),
                            message='Entrez le code temporaire'
                        )
                raise AssertionError('Unhandled authentication flow')
            self.accounts.go(slug=self.SLUG, lang=self.LANG)

    def build_authentication_params(self):
        # Keeping redirect_uri in the state for OTP connections
        # that will need it in finalize_login
        self.redirect_uri = get_url_param(self.url, 'goto')
        return {
            'locale': 'fr',
            'goto': self.redirect_uri,
            'authIndexType': 'service',
            'authIndexValue': 'authn_hsbc_ws',
        }

    def init_login(self):
        # Most of the time, login process is done by posting on the same URL
        # different JSON callbacks that we may have to update with some values
        self.login_page.go(slug=self.SLUG)

        params = self.build_authentication_params()

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

        if self.page.is_device_fingerprint_needed():
            data = self.response.json()

            # set device fingerprint
            # to trigger otp we can just modify userAgent value
            data['callbacks'][0]['input'][0]['value'] = (
                '{"screen":{"screenWidth":1920,"screenHeight":1080,"screenColourDepth":24},'
                + '"timezone":{"timezone":-120},"plugins":{"installedPlugins":""},"fonts":'
                + '{"installedFonts":"cursive;monospace;serif;sans-serif;fantasy;default;'
                + 'Arial;Arial Narrow;Bookman Old Style;Courier;Courier New;Times;Times New Roman;"},'
                + '"userAgent":"Mozilla/5.0 (X11; Linux x86_64; rv:91.0) Gecko/20100101 Firefox/91.0",'
                + '"appName":"Netscape","appCodeName":"Mozilla","appVersion":"5.0 (X11)","platform":'
                + '"Linux x86_64","oscpu":"Linux x86_64","product":"Gecko","productSub":"20100101","language":"en-US"}'
            )

            self.authentication_page.go(json=data)

        return self.response.json()

    def finalize_login(self, token):
        # tokenId allows us to access user_connect_page which itself gives us the final login URL
        self.session.cookies['idtksam'] = token

        self.location(self.redirect_uri)

        # This has the same purpose as in do_login: going to accounts the first time
        # does not redirect to account page but to home page, which will make S2E parent
        # raise a BrowserIncorrectPassword because of a check in the iter_accounts.
        # So, first call to accounts here leads us to home page, then iter_accounts from
        # parent does the request again and this time we're correctly redirected to
        # the real accounts page.
        self.accounts.go(slug=self.SLUG, lang=self.LANG)

    def handle_otp(self):
        self.otp_json['callbacks'][1]['input'][0]['value'] = self.config['otp'].get()

        try:
            self.authentication_page.go(json=self.otp_json)
            data = self.response.json()
            # If OTP is wrong, we can spot it thanks to website
            # response being otp_json again
            if self.page.is_wrong_otp():
                raise BrowserIncorrectPassword(bad_fields=['otp'])
        except ClientError as e:
            if e.response.status_code == 401:
                raise BrowserPasswordExpired('Code de sécurité expiré')
            raise

        # add browser like trusted device
        if self.page.is_json_to_trust_device():
            data['callbacks'][0]['input'][0]['value'] = '0'
            self.authentication_page.go(json=data)

        self.finalize_login(self.response.json().get('tokenId'))
