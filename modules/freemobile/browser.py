# flake8: compatible

# Copyright(C) 2012-2014 Florent Fourcot
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

import itertools
import json

from woob.browser import URL, need_login
from woob.browser.exceptions import ClientError
from woob.browser.filters.standard import QueryValue
from woob.browser.mfa import TwoFactorBrowser
from woob.capabilities.messages import CantSendMessage
from woob.exceptions import (
    ActionNeeded,
    BrowserIncorrectPassword,
    BrowserUnavailable,
    BrowserUserBanned,
    OTPSentType,
    SentOTPQuestion,
)
from woob.tools.decorators import retry

from .pages import (
    CredentialsPage,
    CsrfPage,
    ErrorPage,
    LoginPage,
    LoginRSCPage,
    MainPage,
    OfferPage,
    OptionsPage,
    OtpPage,
    PdfPage,
    ProfilePage,
    ProvidersPage,
    SessionPage,
)


__all__ = ["Freemobile"]


class Freemobile(TwoFactorBrowser):
    BASEURL = "https://mobile.free.fr"

    # 2 following URLs have same value but a is_here is defined in LoginPage and MainPage
    login_page = URL(r"/account/v2/login", LoginPage)
    login_rsc_page = URL(r"/account/v2/login", LoginRSCPage)
    main_page = URL(r"/account/$", MainPage)
    logoutpage = URL(r"/account/\?logout=user", LoginPage)
    pdfpage = URL(r"/account/conso-et-factures\?facture=pdf", PdfPage)
    profile = URL(r"/account/mes-informations", ProfilePage)
    offerpage = URL(r"/account/mon-offre", OfferPage)
    optionspage = URL(r"/account/mes-options", OptionsPage)
    sendAPI = URL(r"https://smsapi.free-mobile.fr/sendmsg\?user=(?P<username>)&pass=(?P<apikey>)&msg=(?P<msg>)")
    error_page = URL(r"/err/oups.html", ErrorPage)
    csrf_token = URL(r"/account/v2/api/auth/csrf", CsrfPage)
    providers = URL(r"/account/v2/api/auth/providers", ProvidersPage)
    credentials = URL(r"/XXXXXXXXXXX", CredentialsPage)
    sessionpage = URL(r"/account/v2/api/auth/session", SessionPage)
    otpemailpage = URL(r"/account/v2/otp.*", OtpPage)

    __states__ = ("otp_id",)

    def __init__(self, config, *args, **kwargs):
        super().__init__(config, *args, **kwargs)
        self.otp_code = config["otp_code"].get()
        self.force_twofa_type_email = config["force_twofa_type_email"].get()

        self.AUTHENTICATION_METHODS = {
            "otp_code": self.handle_otp,
        }

    def clear_init_cookies(self):
        # Keep the trusted-devices cookie to prevent a 2FA
        for cookie in self.session.cookies:
            if cookie.name == "trusted-devices":
                trusted_devices = cookie
                break
        else:
            trusted_devices = None
        self.session.cookies.clear()
        if trusted_devices:
            self.session.cookies.set_cookie(trusted_devices)

    def handle_otp(self):
        error = None
        csrf_token = self.get_csrf_token()
        self.logger.debug("csrf_token: %s", csrf_token)
        try:
            self.credentials.go(
                data={
                    "codeOtp": self.otp_code,
                    "otpId": self.otp_id,
                    "redirect": "false",
                    "isTrusted": "true",
                    "csrfToken": csrf_token,
                    "callbackUrl": "https://mobile.free.fr/account/v2/otp",
                    "json": "true",
                }
            )
            error = self.page.get_error()
        except ClientError as e:
            if e.response.status_code == 401:
                self.logger.debug("e.response.text: %s", e.response.text)
                if not e.response.text:
                    raise BrowserIncorrectPassword()
                json_payload = json.loads(e.response.text)
                if json_payload and ("url" in json_payload):
                    error = QueryValue(None, "error", default=None).filter(json_payload["url"])
            else:
                raise

        if error:
            self.login_page.go(headers={"RSC": "1"})
            error_message = self.page.get_error()
            self.logger.debug("error_message: %s", error_message)
            if error_message == "$undefined":
                error_message = None
            if error == "INVALID_OTP":
                raise BrowserIncorrectPassword(error_message)
            raise BrowserUnavailable(error_message)

    def init_login(self):
        auth_provider = self.get_auth_provider()
        self.logger.debug("auth_provider: %s", auth_provider)
        csrf_token = self.get_csrf_token()
        self.logger.debug("csrf_token: %s", csrf_token)
        self.credentials.urls = [auth_provider.get("callbackUrl")]
        error = None
        try:
            self.credentials.go(
                data={
                    "username": self.username,
                    "password": self.password,
                    "redirect": "false",
                    "csrfToken": csrf_token,
                    "callbackUrl": self.login_page.build(),
                    "json": "true",
                }
            )
            error = self.page.get_error()
        except ClientError as e:
            if e.response.status_code == 401:
                self.logger.debug("e.response.text: %s", e.response.text)
                if not e.response.text:
                    raise BrowserIncorrectPassword()
                json_payload = json.loads(e.response.text)
                if json_payload and ("url" in json_payload):
                    error = QueryValue(None, "error", default=None).filter(json_payload["url"])
            else:
                raise

        self.logger.debug("error: %s", error)

        if error:
            self.login_page.go(headers={"RSC": "1"})
            error_message = self.page.get_error()
            self.logger.debug("error_message: %s", error_message)
            if error_message == "$undefined":
                error_message = error
            if error == "ACCOUNT_BLOCKED":
                raise BrowserUserBanned(error_message)
            elif error == "INVALID_CREDENTIALS":
                raise BrowserIncorrectPassword(error_message)
            raise BrowserUnavailable(error_message)

        self.sessionpage.go()

        twofa_type = self.page.get_2fa_type()
        self.logger.debug("twofa_type: %s", twofa_type)
        self.otp_id = self.page.get_otp_id()
        self.logger.debug("otp_id: %s", self.otp_id)

        medium_type = None

        # By default the (first) 2FA is always sent by SMS.
        # If user prefers an email-based 2FA code (insteas of a SMS-based one),
        # we need a little bit of incantations, and the use of the
        # config parameter `force_twofa_type_email = true`.
        # This tells the code to force the (re)send of a 2FA via email.
        # (Note that it's a new, different 2FA ; not a resend of the previous one).
        # At the moment it seems there is not a way to only send the 2FA via email -
        # there is necessarily a first 2FA sent via SMS, only then will our second 2FA be sent via email.
        #
        # So here we test this flag, emulate the navigation that indicates
        # that we want to send a new 2FA via email, and retrieve the
        # corresponding id (overriding the current -SMS- one)
        if self.otp_id:
            if self.force_twofa_type_email:
                self.otpemailpage.go(
                    data={},
                    headers={"Accept": "text/x-component", "Next-Action": "24ab75ac416eb221418d55a14ba7c79ad34bea7d"},
                    json=[self.username],
                )
                self.otp_id = self.page.get_otp_id()
                self.otpemailpage.go(
                    params={"otpId": self.otp_id},
                    headers={"Accept": "text/x-component", "RSC": "1"},
                )
                medium_type = OTPSentType.EMAIL

        if not medium_type:
            if twofa_type and self.otp_id:
                medium_type = OTPSentType.UNKNOWN
                if twofa_type == "sms":
                    medium_type = OTPSentType.SMS
                elif twofa_type == "email":
                    medium_type = OTPSentType.EMAIL

        if medium_type:
            raise SentOTPQuestion(
                field_name="otp_code", medium_type=medium_type, message="Please type the OTP you received"
            )

    @retry(BrowserUnavailable)
    def send_credentials(self):
        self.page.login(self.username, self.password)
        if self.error_page.is_here():
            self.logger.warning("We are on error_page, we retry")
            self.session.cookies.clear()
            self.login_page.go()
            raise BrowserUnavailable()

    def do_logout(self):
        self.logoutpage.go()
        self.session.cookies.clear()

    def get_csrf_token(self):
        return self.csrf_token.go().get_token()

    def get_auth_provider(self):
        return self.providers.go().get_auth_provider()

    @need_login
    def iter_subscription(self):
        self.offerpage.stay_or_go()
        if self.login_page.is_here():
            error = self.page.get_error()
            if "restreint suite à un impayé" in error:
                raise ActionNeeded(error)
            elif "Vous ne pouvez pas avoir accès à cette page" in error:
                raise BrowserUnavailable(error)
            elif error:
                raise AssertionError("Unexpected error at subscription: %s" % error)

        if self.main_page.is_here():
            msg = self.page.get_information_message()

            if "pas avoir accès à cette page pour le moment car votre espace abonné a été restreint " in msg:
                raise BrowserUserBanned(msg)

        # Recaps are only available on the first subscription, so if not
        # selected, we want to force select it here.
        first_subscription_id = self.page.get_first_subscription_id()
        if first_subscription_id:
            self.main_page.go(params={"switch-user": first_subscription_id})
            self.offerpage.go()

        subscriptions = itertools.chain([self.page.get_first_subscription()], self.page.iter_next_subscription())

        first_subscription = None
        has_multiple_subs = False

        for subscription in subscriptions:
            self.main_page.go(params={"switch-user": subscription.id})
            self.offerpage.go()
            self.page.fill_subscription(subscription)
            if first_subscription is None:
                first_subscription = subscription
            else:
                has_multiple_subs = True
            yield subscription

        if has_multiple_subs:
            s = first_subscription.copy()
            s.label = f"Récapitulatif facture des lignes de l'identifiant {s.id}"
            s.id = f"R{s.id}"
            s._is_recapitulatif = True
            yield s

    @need_login
    def iter_documents(self, subscription):
        self.main_page.go(params={"switch-user": subscription._real_id})
        return self.page.iter_documents(sub=subscription.id, is_recapitulatif=subscription._is_recapitulatif)

    @need_login
    def post_message(self, message):
        receiver = message.thread.id
        username = [
            subscription._real_id
            for subscription in self.iter_subscription()
            if subscription._phone_number.split("@")[0] == receiver
        ]
        if username:
            username = username[0]
        else:
            raise CantSendMessage("Cannot fetch own number.")

        self.login_page.go(params={"switch-user": username})
        self.optionspage.go()

        api_key = self.page.get_api_key()
        if not api_key:
            raise CantSendMessage("Cannot fetch API key for this account, is option enabled?")

        self.sendAPI.go(username=username, apikey=api_key, msg=message.content)

    @need_login
    def get_profile(self):
        self.profile.go()
        return self.page.get_profile()
