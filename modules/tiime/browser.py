# -*- coding: utf-8 -*-

# Copyright(C) 2022      Jeremy Demange (scrapfast.io)
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

from __future__ import unicode_literals


import random
import string

from woob.browser import LoginBrowser, StatesMixin, URL, need_login
from woob.browser.exceptions import ClientError

import re

from .pages import Page1, Page2


class TiimeBrowser(LoginBrowser, StatesMixin):
    BASEURL = 'https://apps.tiime.fr/'

    login = URL('https://auth0.tiime.fr/co/authenticate')
    login_redirect = URL(r'https://auth0.tiime.fr/authorize\?client_id=(?P<client_id>)&response_type=token%20id_token&redirect_uri=https%3A%2F%2Fapps.tiime.fr%2Fauth-callback%3Flogin_initiator%3Duser&scope=openid%20email&audience=https%3A%2F%2Fchronos-prod-api%2F&realm=Chronos-prod-db&state=(?P<state>)&nonce=(?P<nonce>)&login_ticket=(?P<login_ticket>)&auth0Client=(?P<auth_zero_client>)')
    get_jwks = URL('https://auth0.tiime.fr/.well-known/jwks.json')

    my_informations = URL("https://chronos-api.tiime-apps.com/v1/users/me")

    token_regexp = re.compile(r'access\_token\S{975}')

    __states__ = ["token"]

    def __init__(self, username, password, *args, **kwargs):
        super().__init__(username, password, *args, **kwargs)
        self.token = None

    def generate_nonce(self, length=32):
        generate = ''
        while length > 0:
            generate += random.choice(string.ascii_letters)
            length -= 1
        return generate

    def do_login(self):
        if not self.token:
            client_id_auth_app = "iEbsbe3o66gcTBfGRa012kj1Rb6vjAND"
            auth_zero_client = "eyJuYW1lIjoiYXV0aDAuanMiLCJ2ZXJzaW9uIjoiOS4xNi4wIn0="

            state = self.generate_nonce()
            nonce = self.generate_nonce()

            try:
                self.login.go(method="POST", headers={
                    "auth0-client": auth_zero_client,
                    "origin": "https://apps.tiime.fr",
                    "referer": "https://apps.tiime.fr/"}, json={
                    "client_id": client_id_auth_app,
                    "username": self.username,
                    "password": self.password,
                    "realm": "Chronos-prod-db",
                    "credential_type": "http://auth0.com/oauth/grant-type/password-realm"
                })
            except ClientError as e:
                result = e.response.json()
                print(result)
                raise

            response = self.response.json()
            login_ticket = response["login_ticket"]

            try:
                self.login_redirect.go(client_id=client_id_auth_app, state=state, nonce=nonce, login_ticket=login_ticket, auth_zero_client= auth_zero_client)
                gettoken = self.response.url
                mo = self.token_regexp.search(gettoken)
                token = mo.group()
                self.token = token.replace("access_token=", "")
            except ClientError as e:
                result = e.response.json()
                print(result)
                raise

    @need_login
    def get_profile(self):
        self.my_informations.go(headers={"authorization": "Bearer " + self.token})
        result = self.response.json()
        print(result)
        return []

    @need_login
    def iter_history(self):
        return []

    @need_login
    def iter_accounts(self):
        return []