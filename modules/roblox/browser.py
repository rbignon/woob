# flake8: compatible

# Copyright(C) 2022 Thomas Touhey <thomas@touhey.fr>
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

from woob.browser.browsers import need_login
from woob.browser.mfa import TwoFactorBrowser
from woob.browser.url import URL, BrowserParamURL
from woob.exceptions import BrowserUserBanned, OfflineOTPQuestion, OTPSentType, SentOTPQuestion
from woob.tools.capabilities.bank.transactions import sorted_transactions

from .pages import (
    AccountPage,
    BirthdateAPIPage,
    CaptchaMetadataAPIPage,
    CurrencyAPIPage,
    EmailAPIPage,
    ErrorAPIPage,
    GenderAPIPage,
    InventoryPage,
    LoginAPIPage,
    LoginPage,
    PhoneAPIPage,
    TransactionsAPIPage,
    TwoFAValidateChallengeAPIPage,
    ValidateTwoFAAPIPage,
)
from .utils import get_username_type


class RobloxBrowser(TwoFactorBrowser):
    BASEURL = "https://www.roblox.com/"

    login_page = URL(r"login", LoginPage)
    account_page = URL(r"my/account", AccountPage)

    inventory_page = URL(
        r"users/inventory/list-json",
        InventoryPage,
    )

    login_api_page = URL(
        r"https://auth.roblox.com/v2/login",
        LoginAPIPage,
    )
    validate_twofa_api_page = BrowserParamURL(
        r"https://auth.roblox.com/v3/users/(?P<browser_user_id>\d+)" + r"/two-step-verification/login",
        ValidateTwoFAAPIPage,
    )

    captcha_metadata_api_page = URL(
        r"https://apis.rbxcdn.com/captcha/v1/metadata",
        CaptchaMetadataAPIPage,
    )

    twofa_validate_challenge_api_page = BrowserParamURL(
        r"https://twostepverification.roblox.com/v1/users/"
        + r"(?P<browser_user_id>\d+)/challenges/(?P<challenge_type>\w+)"
        + r"/verify",
        TwoFAValidateChallengeAPIPage,
    )

    email_api_page = URL(
        r"https://accountsettings.roblox.com/v1/email",
        EmailAPIPage,
    )
    phone_api_page = URL(
        r"https://accountinformation.roblox.com/v1/phone",
        PhoneAPIPage,
    )
    birthdate_api_page = URL(
        r"https://accountinformation.roblox.com/v1/birthdate",
        BirthdateAPIPage,
    )
    gender_api_page = URL(
        r"https://accountinformation.roblox.com/v1/gender",
        GenderAPIPage,
    )
    currency_api_page = BrowserParamURL(
        r"https://economy.roblox.com/v1/users/(?P<browser_user_id>\d+)" + r"/currency",
        CurrencyAPIPage,
    )
    transactions_api_page = BrowserParamURL(
        r"https://economy.roblox.com/v2/users/(?P<browser_user_id>\d+)" + r"/transactions",
        TransactionsAPIPage,
    )

    def __init__(self, config, *args, **kwargs):
        super().__init__(
            config,
            config["login"].get(),
            config["password"].get(),
            *args,
            **kwargs,
        )

        # Add authentication methods.
        self.AUTHENTICATION_METHODS = {
            "captcha_response": self.init_login,
            "otp_email": self.do_otp_email,
            "otp_authenticator": self.do_otp_authenticator,
        }

        # Add more stored properties for login.
        self.captcha_id = None
        self.user_id = None
        self.ticket_id = None
        self.__states__ += ("captcha_id", "user_id", "ticket_id")

    def raise_for_status(self, response):
        if 400 <= response.status_code < 600:
            # Try to parse an API-like status.

            try:
                page = ErrorAPIPage(self, response)
            except (TypeError, ValueError, KeyError):
                pass
            else:
                page.raise_if_error()

        return super().raise_for_status(response)

    def init_login(self):
        data = {
            "ctype": get_username_type(self.username),
            "cvalue": self.username,
            "password": self.password,
        }

        if hasattr(self, "captcha_response") and self.captcha_response:
            data.update(
                {
                    "captchaId": self.captcha_id,
                    "captchaToken": self.captcha_response,
                }
            )

        # Can already be there in case of captcha.
        self.login_page.stay_or_go()

        headers = {}
        csrf_token = self.page.get_csrf_token()
        if csrf_token:
            headers["x-csrf-token"] = csrf_token

        page = self.login_api_page.open(json=data, headers=headers)
        self.user_id = page.get_user_id()

        if page.is_banned():
            # TODO: Theoretical case, find out the message that appears here.
            raise BrowserUserBanned("Player is banned")

        second_factor = page.get_second_factor()
        if second_factor is not None:
            self.ticket_id = second_factor["ticket"]

            if second_factor["type"] == "Email":
                raise SentOTPQuestion(
                    "otp_email",
                    message="Saisir le code que nous venons de t'envoyer par e-mail.",
                    medium_type=OTPSentType.EMAIL,
                )
            elif second_factor["type"] == "Authenticator":
                raise OfflineOTPQuestion(
                    "otp_authenticator",
                    message="Entrer le code généré par ton application d'authentification.",
                )

            raise AssertionError(f'Unknown mediumType {second_factor["type"]!r}')

        # Go on the account page, which is a logged page.
        self.account_page.go()
        if not self.user_id:
            self.user_id = self.page.get_user_id()

    def do_otp_email(self):
        self.do_twofa_challenge(
            challenge_type="email",
            challenge_code=self.otp_email,
        )

    def do_otp_authenticator(self):
        self.do_twofa_challenge(
            challenge_type="authenticator",
            challenge_code=self.otp_authenticator,
        )

    def do_twofa_challenge(self, challenge_type, challenge_code):
        headers = {}
        csrf_token = self.page.get_csrf_token()
        if csrf_token:
            headers["x-csrf-token"] = csrf_token

        page = self.twofa_validate_challenge_api_page.open(
            challenge_type=challenge_type,
            headers=headers,
            json={
                "challengeId": self.ticket_id,
                "actionType": "Login",
                "code": challenge_code,
            },
        )

        validation_token = page.get_verification_token()
        self.validate_twofa_api_page.open(
            headers=headers,
            json={
                "challengeId": self.ticket_id,
                "rememberDevice": True,
                "verificationToken": validation_token,
            },
        )

        # Go on the account page in order to get a logged page.
        self.account_page.go()

    @need_login
    def get_account(self):
        self.account_page.stay_or_go()
        account = self.page.get_account()

        self.currency_api_page.open().get_account(obj=account)
        return account

    @need_login
    def iter_history(self):
        def inner(self):
            """Yield transactions from all pages, for later sorting"""
            for type_ in ("CurrencyPurchase", "Purchase"):
                self.transactions_api_page.go(
                    params={
                        "transactionType": type_,
                        "limit": "100",
                    }
                )
                yield from self.page.iter_history()

        return sorted_transactions(inner(self))

    @need_login
    def get_profile(self):
        self.account_page.stay_or_go()
        profile = self.page.get_profile()

        self.email_api_page.open().get_profile(obj=profile)
        self.phone_api_page.open().get_profile(obj=profile)
        self.birthdate_api_page.open().get_profile(obj=profile)
        self.gender_api_page.open().get_profile(obj=profile)

        return profile

    @need_login
    def iter_investment(self):
        # TODO: Leave itemsPerPage at 10 in order to find out how to
        #       manage pagination.
        self.inventory_page.go(
            params={
                "itemsPerPage": 10,  # 10, 25, 50 or 100
                "pageNumber": 1,
                "assetTypeId": 8,
                "userId": self.user_id,
            }
        )

        investments = {}
        for inv in self.page.iter_investment():
            other_inv = investments.get(inv.id)
            if not other_inv:
                investments[inv.id] = inv
            else:
                other_inv.quantity += inv.quantity
                other_inv.valuation += inv.valuation

        yield from investments.values()
