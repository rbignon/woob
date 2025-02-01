# -*- coding: utf-8 -*-

# Copyright(C) 2016      Benjamin Bouvier
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

import time
from datetime import datetime, timedelta
from uuid import uuid4

from woob.browser.browsers import need_login
from woob.browser.exceptions import BrowserTooManyRequests, ClientError
from woob.browser.mfa import TwoFactorBrowser
from woob.browser.url import URL
from woob.capabilities.bank import AccountNotFound
from woob.capabilities.base import find_object
from woob.exceptions import (
    AppValidation,
    AppValidationCancelled,
    AppValidationExpired,
    BrowserIncorrectPassword,
    BrowserUnavailable,
    BrowserUserBanned,
    OTPSentType,
    SentOTPQuestion,
)
from woob.tools.capabilities.bank.transactions import sorted_transactions
from woob.tools.date import now_as_utc

from .pages import AccountPage, SpacesPage, TransactionsCategoryPage, TransactionsPage


class Number26Browser(TwoFactorBrowser):
    # Password encoded in base64 for the initial basic-auth scheme used to
    # get an access token.
    INITIAL_TOKEN = "bmF0aXZld2ViOg=="

    HAS_CREDENTIALS_ONLY = True

    twofa_challenge = URL(r"/api/mfa/challenge")
    access_token_url = URL(r"/oauth2/token")
    account = URL(r"/api/accounts", AccountPage)
    spaces = URL(r"/api/spaces", SpacesPage)
    transactions = URL(r"/api/smrt/transactions", TransactionsPage)
    categories = URL(r"/api/smrt/categories", TransactionsCategoryPage)

    def __init__(self, config, *args, **kwargs):
        kwargs["username"] = config["login"].get()
        kwargs["password"] = config["password"].get()
        super(Number26Browser, self).__init__(config, *args, **kwargs)
        self.mfa_token = None  # Token associated with a 2FA session.
        self.refresh_token = None
        self.access_token = None
        self.token_expire = None
        # An uuid4 token used to represent the device. Must be kept in the
        # state across reuses.
        self.device_token = str(uuid4())
        self.is_first_sync = False
        # do not delete, useful for a child connector
        self.direct_access = True
        self.BASEURL = "https://api.tech26.de"

        self.__states__ = (
            "access_token",
            "device_token",
            "is_first_sync",
            "mfa_token",
            "refresh_token",
            "token_expire",
        )

        self.AUTHENTICATION_METHODS = {
            "resume": self.handle_polling,
            "otp": self.handle_otp,
        }

    def build_request(self, *args, **kwargs):
        headers = kwargs.setdefault("headers", {})

        headers["Authorization"] = "Basic %s" % self.INITIAL_TOKEN
        if self.logged:
            headers["Authorization"] = "Bearer %s" % self.access_token

        headers["Accept"] = "application/json"
        headers["device-token"] = self.device_token

        req = super(Number26Browser, self).build_request(*args, **kwargs)
        return req

    def locate_browser(self, state):
        pass

    def raise_for_status(self, response):
        if response.status_code == 401:
            self.access_token = None

        return super(Number26Browser, self).raise_for_status(response)

    @property
    def logged(self):
        return (
            self.access_token
            and self.token_expire
            and datetime.strptime(self.token_expire, "%Y-%m-%d %H:%M:%S") > datetime.now()
        )

    def init_login(self):
        # The refresh token lasts between one and two hours, be carefull, otp asked frequently
        if self.refresh_token:
            if self.has_refreshed():
                return

        # If we do not have a refresh token and the session is not interactive,
        # the server will respond with a 451 error.
        # Plus, not having a refresh token means that we'll have to perform 2FA.
        self.check_interactive()

        data = {
            "username": self.username,
            "password": self.password,
            "grant_type": "password",
        }
        try:
            self.access_token_url.go(data=data)
        except ClientError as e:
            # Sometimes we get a random 405 back from our first request, there is no response body.
            if e.response.status_code == 405:
                raise BrowserUnavailable()

            if e.response.status_code == 429:
                # if we try too many requests, it will return a 429 and the user will have
                # to wait 30 minutes before retrying, and if he retries at 29 min, he will have
                # to wait 30 minutes more
                raise BrowserTooManyRequests()

            if e.response.status_code == 451:
                # 451 Unavailable For Legal Reasons
                # Under special circumstances, the user ip address has to be provided with a specific
                # header, otherwise this error is to be encountered.
                raise AssertionError("No x-tpp-userip header was provided")

            json_response = e.response.json()
            if json_response.get("title") == "A second authentication factor is required.":

                self.is_first_sync = True
                self.mfa_token = json_response["mfaToken"]
                self.trigger_2fa()

            elif json_response.get("error") == "invalid_grant":
                raise BrowserIncorrectPassword(json_response["error_description"])

            elif json_response.get("title") == "Error":
                raise BrowserUnavailable(json_response["message"])
            raise

        result = self.response.json()
        self.update_token(result["access_token"], result["refresh_token"], result["expires_in"])

    def has_refreshed(self):
        data = {
            "refresh_token": self.refresh_token,
            "grant_type": "refresh_token",
        }
        try:
            self.access_token_url.go(data=data)
        except ClientError as e:
            # sometimes response is empty so don't try to use 'json()' if it's not necessary
            if e.response.status_code == 401:
                # The refresh token has expired.
                self.refresh_token = None
                self.access_token = None
                self.token_expire = None
                return False

            if e.response.status_code == 429:
                raise BrowserTooManyRequests()

            raise

        result = self.response.json()
        self.update_token(result["access_token"], result["refresh_token"], result["expires_in"])
        return True

    def update_token(self, access_token, refresh_token, expires_in):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.token_expire = (datetime.now() + timedelta(seconds=expires_in)).strftime("%Y-%m-%d %H:%M:%S")

    def trigger_2fa(self):
        data = {
            "challengeType": "oob",  # AppVal
            "mfaToken": self.mfa_token,
        }
        try:
            # We first check if we can do an AppVal as it is better than SMS
            # (From the doc: SMS delivery rate is not 100%, takes time and is limited).
            self.twofa_challenge.go(json=data)
        except ClientError as e:
            if e.response.status_code != 403:
                # 403 means that the PSU has no paired device.
                # In that case we fallback to OTP 2FA.
                raise
        else:
            raise AppValidation(
                "Veuillez autoriser la demande d'accès aux informations de votre compte dans l'application."
            )

        data["challengeType"] = "otp"

        try:
            self.twofa_challenge.go(json=data)
        except ClientError as e:
            json_response = e.response.json()
            # if we send more than 5 otp without success, the server will warn the user to
            # wait 12h before retrying, but in fact it seems that we can resend otp 5 mins later
            if e.response.status_code == 429:
                raise BrowserUserBanned(json_response["detail"])
            raise

        result = self.response.json()
        raise SentOTPQuestion(
            "otp",
            medium_type=OTPSentType.SMS,
            message="Veuillez entrer le code reçu par sms au %s" % result["obfuscatedPhoneNumber"],
        )

    def handle_polling(self):
        data = {
            "mfaToken": self.mfa_token,
            "grant_type": "mfa_oob",
        }
        self.mfa_token = None  # To make sure we don't reuse it if something goes wrong.

        timeout = time.time() + 5 * 60.0
        while time.time() < timeout:
            try:
                self.access_token_url.go(data=data)
            except ClientError as e:
                json_response = e.response.json()
                error = json_response.get("error")
                if error:
                    if error == "authorization_pending":
                        time.sleep(5)
                        continue
                    elif error == "invalid_grant":
                        raise AppValidationCancelled("L'opération dans votre application a été annulée.")
                raise
            else:
                result = self.response.json()
                self.update_token(result["access_token"], result["refresh_token"], result["expires_in"])
                return

        raise AppValidationExpired("L'opération dans votre application a expiré.")

    def handle_otp(self):
        mfa_token = self.mfa_token
        self.mfa_token = None

        data = {
            "mfaToken": mfa_token,
            "grant_type": "mfa_otp",
            "otp": self.otp,
        }

        try:
            self.access_token_url.go(data=data)
        except ClientError as e:
            json_response = e.response.json()
            error = json_response.get("error")
            if error:
                if error == "invalid_otp":
                    # In case of a wrong OTP, we need to keep the same mfaToken before prompting
                    # the PSU to try again as it's the same 2FA session.
                    self.mfa_token = mfa_token
                    raise SentOTPQuestion(
                        "otp",
                        medium_type=OTPSentType.SMS,
                        message="Le code que vous avez entré est invalide, veuillez réessayer.",
                    )
                elif error == "too_many_attempts":
                    # We need to resend an SMS.
                    self.init_login()
                elif error == "invalid_grant":
                    # The mfaToken has expired, this 2FA session is no longer valid.
                    self.init_login()
            raise

        result = self.response.json()
        self.update_token(result["access_token"], result["refresh_token"], result["expires_in"])

    @need_login
    def iter_accounts(self):
        self.account.go()

        # N26 only provides a unique checking account.
        account = self.page.get_account()

        # Spaces can be created by the PSU, he can transfer/withdraw
        # money between these spaces.
        #
        # A space is not an account in its own right, so we consider the checking account
        # balance to be the total balance spread over all the spaces.
        self.spaces.go()
        self.page.fill_account(obj=account)

        return [account]

    @need_login
    def get_account(self, _id):
        return find_object(self.iter_accounts(), id=_id, error=AccountNotFound)

    @need_login
    def get_categories(self):
        """
        Generates a map of categoryId -> categoryName, for fast lookup when
        fetching transactions.
        """
        self.categories.go()
        return self.page.get_categories()

    @need_login
    def iter_history(self, categories):
        return self._iter_transactions(categories)

    @need_login
    def iter_coming(self, categories):
        return self._iter_transactions(categories, coming=True)

    @need_login
    def _iter_transactions(self, categories, coming=False):
        params = {"limit": 1000}
        if not self.is_first_sync:
            # When using an access token generated using a refresh token,
            # we can only retrieve 90 days of transactions.
            now = now_as_utc()
            params["from"] = (int((now - timedelta(days=90)).timestamp() * 1000),)
            params["to"] = (int(now.timestamp() * 1000),)
        else:
            self.is_first_sync = False

        self.transactions.go(params=params)
        for tr in sorted_transactions(self.page.iter_history(coming=coming)):
            if self.direct_access:
                tr.category = categories[tr._category_id]

            yield tr
