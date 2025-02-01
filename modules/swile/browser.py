# Copyright(C) 2018      Roger Philibert
#
# This file is part of woob.
#
# woob is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# woob is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with woob. If not, see <http://www.gnu.org/licenses/>.

# flake8: compatible

from datetime import date, timedelta
from functools import wraps

from woob.browser.browsers import APIBrowser, OAuth2Mixin
from woob.browser.exceptions import BrowserTooManyRequests, ClientError
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import CleanDecimal, CleanText, Currency, DateTime, Format
from woob.capabilities.bank import Account, Transaction
from woob.capabilities.base import empty
from woob.capabilities.captcha import RecaptchaV3Question
from woob.exceptions import BrowserIncorrectPassword, BrowserUserBanned, WrongCaptchaResponse


def need_login(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.logged:
            self.do_login()
        return func(self, *args, **kwargs)

    return wrapper


class SwileBrowser(OAuth2Mixin, APIBrowser):
    BASEURL = "https://customer-api.swile.co"
    ACCESS_TOKEN_URI = "https://directory.swile.co/oauth/token"
    client_id = "533bf5c8dbd05ef18fd01e2bbbab3d7f69e3511dd08402862b5de63b9a238923"

    def __init__(self, config, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session.headers["X-API-Key"] = "50558e8b836b7a8e089c35b7b58a1d3959ca56d6"
        self.session.headers["X-Lunchr-Platform"] = "web"
        self.session.headers["X-Lunchr-App-Version"] = "0.1.0"
        self.credentials = {
            "client_id": self.client_id,
            "grant_type": "password",
            "username": config["login"].get(),
            "password": config["password"].get(),
        }
        self.config = config

    def request_authorization(self):
        try:
            if self.config["captcha_response"].get():
                self.credentials["recaptcha_enterprise_token"] = self.config["captcha_response"].get()
            self.location(self.ACCESS_TOKEN_URI, data=self.credentials)
        except ClientError as e:
            if e.response.status_code == 401:
                if not self.config["captcha_response"].get():
                    raise RecaptchaV3Question(
                        website_url="https://app.swile.co/signin",
                        website_key="6LfrQZEdAAAAAJZF_2WDGlcqQ_6hNIN55Mi7Eiyn",
                        is_enterprise=True,
                        action="login",
                    )
                elif not e.response.json():
                    # Captcha is wrong when empty json is returned
                    raise WrongCaptchaResponse()

            json = e.response.json()
            message = json.get("error_description", "")
            if e.response.status_code == 400:
                if "authorization grant is invalid, expired, revoked" in message:
                    # JS interprets this message as wrongpass
                    raise BrowserIncorrectPassword()
            # sometimes we get a 401 error with an invalid token when we try to connect several times
            # with wrong creds to our swile account
            if e.response.status_code == 401:
                error = json.get("error", "")
                error_code = json.get("error_code", "")
                if error == "invalid_token":
                    if "try again later" in message.lower():
                        raise BrowserUserBanned(message)
                    # we can also get a wrongcaptcha error due to these wrong creds (conclusion of several tests)
                    elif "recaptcha_invalid_token" in error_code.lower():
                        raise WrongCaptchaResponse(error_code)

            if e.response.status_code == 429:
                raise BrowserTooManyRequests()

            raise AssertionError(f"Unhandled error message during login: {message}")

        self.update_token(self.response.json())

    @need_login
    def get_me(self):
        return self.request(self.absurl("/api/v0/users/me", base=self.BASEURL))["user"]

    @need_login
    def get_account(self):
        json = self.get_me()
        account = Account()

        account.id = CleanText(Dict("id"))(json)
        account.number = account.id
        account.bank_name = "Swile"

        account.type = Account.TYPE_CHECKING

        # Check if account have a card
        balance = Dict("meal_voucher_info/balance/value", default=None)(json)
        if empty(balance):
            return

        account.balance = CleanDecimal.SI(balance)(json)
        account.label = Format("%s %s", CleanText(Dict("first_name")), CleanText(Dict("last_name")))(json)
        account.currency = Currency(Dict("meal_voucher_info/balance/currency/iso_3"))(json)
        account.cardlimit = CleanDecimal.SI(Dict("meal_voucher_info/daily_balance/value"))(json)
        yield account

    @need_login
    def iter_history(self, account):
        # make sure we have today's transactions
        before = date.today() + timedelta(days=1)

        for _ in range(200):  # limit pagination
            response = self.open(
                "https://banking-api.swile.co/api/v0/payments_history",
                params={
                    "per": 20,
                    "before": before.isoformat(),
                    # don't pass page= param, it works but
                    # it's slower than the before= param
                },
            )
            json = response.json()
            if len(Dict("payments_history")(json)) == 0:
                break

            has_transactions = False
            for payment in Dict("payments_history")(json):
                if "refunding_transaction" in payment:
                    refund = self._parse_transaction(payment["refunding_transaction"])
                    refund.type = Transaction.TYPE_CARD
                    yield refund

                    has_transactions = True

                transaction = self._parse_transaction(payment)
                if transaction:
                    # this is a millisecond-precise datetime (with a timezone).
                    # fortunately, the api excludes transactions occuring at the exact datetime we pass.
                    # if the page boundary is hit on transactions occurring at the same datetime, we might lose some of them though.
                    before = transaction.date

                    yield transaction

                    has_transactions = True

            if not has_transactions:
                break
        else:
            raise Exception("that's a lot of transactions, probable infinite loop?")

    def _parse_transaction(self, payment):
        # Different types of payment
        # ORDER = order on swile website
        # LUNCHR_CARD_PAYMENT = pay in shop
        # PAYMENT = pay with swile card or/and linked bank card
        # MEAL_VOUCHER_CREDIT = refund
        transaction = Transaction()
        transaction_id = Dict("transaction_number", default=None)(payment)
        # Check if transaction_id is None or declined date exists which indicates failed transaction
        if transaction_id is None or Dict("declined_at", default=None)(payment):
            return

        # Check if transaction is only on cb card
        # if 'details' is empty we put default on '' because it's probably a
        # 'MEAL_VOUCHER_RENEWAL' or a 'MEAL_VOUCHER_EXPIRATION'
        if (
            Dict("type")(payment) != "MEAL_VOUCHER_CREDIT"
            and len(Dict("details", default="")(payment)) == 1
            and Dict("details/0/type")(payment) == "CREDIT_CARD"
        ):
            return

        # special case, if the payment is made from the platform with a card not linked to the swile card
        if Dict("type")(payment) == "ORDER" and not Dict("details")(payment):
            return

        transaction.id = transaction_id
        transaction.date = DateTime(Dict("executed_at"))(payment)
        transaction.rdate = DateTime(Dict("created_at"))(payment)
        transaction.label = Dict("name")(payment)
        if Dict("type")(payment) == "MEAL_VOUCHER_CREDIT":
            transaction.amount = CleanDecimal.US(Dict("amount/value"))(payment)
            transaction.type = Transaction.TYPE_DEPOSIT
        elif Dict("type")(payment) in ("MEAL_VOUCHER_RENEWAL", "MEAL_VOUCHER_EXPIRATION"):
            transaction.amount = CleanDecimal.US(Dict("amount/value"))(payment)
            transaction.type = Transaction.TYPE_BANK
        else:
            transaction.amount = CleanDecimal.US(Dict("details/0/amount"))(payment)
            transaction.type = Transaction.TYPE_CARD

        return transaction
