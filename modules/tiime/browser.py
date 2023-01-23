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

# flake8: compatible

import re
import random
import string
from datetime import datetime

from woob.browser import LoginBrowser, StatesMixin, URL, need_login
from woob.browser.exceptions import ClientError
from woob.capabilities.bank import Account, Transaction
from woob.capabilities.profile import Profile
from woob.exceptions import (
    BrowserUnavailable, BrowserIncorrectPassword, BrowserPasswordExpired,
)


class TiimeBrowser(LoginBrowser, StatesMixin):
    BASEURL = 'https://apps.tiime.fr/'

    login = URL('https://auth0.tiime.fr/co/authenticate')
    login_redirect = URL(r'https://auth0.tiime.fr/authorize\?client_id=(?P<client_id>)&response_type=token%20id_token&redirect_uri=https%3A%2F%2Fapps.tiime.fr%2Fauth-callback%3Flogin_initiator%3Duser&scope=openid%20email&audience=https%3A%2F%2Fchronos-prod-api%2F&realm=Chronos-prod-db&state=(?P<state>)&nonce=(?P<nonce>)&login_ticket=(?P<login_ticket>)&auth0Client=(?P<auth_zero_client>)')

    my_informations = URL("https://chronos-api.tiime-apps.com/v1/users/me")
    my_account = URL(r"https://chronos-api.tiime-apps.com/v1/companies/(?P<company_id>)/bank_accounts\?enabled=true")
    my_transactions = URL(r"https://chronos-api.tiime-apps.com/v1/companies/(?P<company_id>)/bank_transactions\?hide_refused=false&bank_account=(?P<account_id>)")
    token_regexp = re.compile(r'access\_token\S{975}')

    # TODO: add states & refresh token later
    # __states__ = ["token", "company_id"]

    def __init__(self, username, password, *args, **kwargs):
        super().__init__(username, password, *args, **kwargs)
        self.token = None
        self.company_id = None

    @staticmethod
    def generate_nonce(length=32):
        generate = ''
        while length > 0:
            generate += random.choice(string.ascii_letters)
            length -= 1

        return generate

    def raise_for_status(self, response):
        if response.status_code == 401:
            self.token = None
            raise BrowserPasswordExpired("Votre session a expiré.")

        super().raise_for_status(response)

    def do_login(self):
        if self.token:
            return

        # Tiime keys for Auth0
        client_id_auth_app = "iEbsbe3o66gcTBfGRa012kj1Rb6vjAND"
        auth_zero_client = "eyJuYW1lIjoiYXV0aDAuanMiLCJ2ZXJzaW9uIjoiOS4xNi4wIn0="

        state = self.generate_nonce()
        nonce = self.generate_nonce()

        try:
            self.login.go(
                headers={
                    "auth0-client": auth_zero_client,
                    "origin": "https://apps.tiime.fr",
                    "referer": "https://apps.tiime.fr/",
                },
                json={
                    "client_id": client_id_auth_app,
                    "username": self.username,
                    "password": self.password,
                    "realm": "Chronos-prod-db",
                    "credential_type": "http://auth0.com/oauth/grant-type/password-realm",
                },
            )
        except ClientError as e:
            if e.response.status_code == 402:
                raise BrowserIncorrectPassword("Email ou mot de passe incorrect.")

            result = e.response.json()
            raise BrowserUnavailable(result)

        response = self.response.json()
        login_ticket = response["login_ticket"]

        try:
            self.login_redirect.go(
                client_id=client_id_auth_app, state=state, nonce=nonce,
                login_ticket=login_ticket, auth_zero_client=auth_zero_client,
            )
            gettoken = self.response.url
            try:
                mo = self.token_regexp.search(gettoken)
                token = mo.group()
                self.token = token.replace("access_token=", "")
            except Exception:
                raise BrowserUnavailable("Impossible de trouver le token d'accès.")
        except ClientError as e:
            result = e.response.json()
            raise BrowserUnavailable(result)

        self.session.headers['authorization'] = "Bearer " + self.token

    @need_login
    def get_company_id(self):
        if self.company_id:
            return

        try:
            self.my_informations.go()
        except ClientError as e:
            result = e.response.json()
            raise BrowserUnavailable(result)

        result = self.response.json()
        self.company_id = result["companies"][0]["id"]

    @need_login
    def get_profile(self):
        try:
            self.my_informations.go()
        except ClientError as e:
            result = e.response.json()
            raise BrowserUnavailable(result)

        result = self.response.json()
        pr = Profile()
        pr.name = result["firstname"] + " " + result["lastname"]
        pr.email = result["email"]
        pr.address = (
            result["mailing_street"] + " - " + result["mailing_city"]
            + ", " + result["mailing_postal_code"]
        )
        pr.country = result["nationality"]
        pr.phone = result["phone"]
        pr.id = result["id"]
        return pr

    @need_login
    def iter_history(self, account_id):
        self.get_company_id()
        try:
            self.my_transactions.go(
                company_id=self.company_id, account_id=account_id.id,
                headers={"Range": "items=0-100"},
            )
        except ClientError as e:
            result = e.response.json()
            raise BrowserUnavailable(result)

        result = self.response.json()
        transactions = []
        for tr in result:
            t = Transaction()
            t.id = tr["id"]
            t.amount = tr["amount"]
            t.label = tr["original_wording"]
            t.date = datetime.strptime(tr["transaction_date"], '%Y-%m-%d')
            transactions.append(t)

        return transactions

    @need_login
    def iter_accounts(self):
        self.get_company_id()
        try:
            self.my_account.go(company_id=self.company_id)
        except ClientError as e:
            result = e.response.json()
            raise BrowserUnavailable(result)

        result = self.response.json()
        accounts = []
        for acc in result:
            a = Account()
            a.id = acc["id"]
            a.balance = acc["balance_amount"]
            a.bank_name = a.label = acc["bank_name"]
            a.iban = acc["iban"]
            a.currency = acc["balance_currency"]
            a.type = Account.TYPE_CHECKING
            accounts.append(a)

        return accounts
