# Copyright(C) 2019 Powens
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

import random
import re
import string
from math import floor
from urllib.parse import parse_qsl, urlparse

from jose import jwt

from woob.browser import URL, need_login
from woob.browser.exceptions import ClientError
from woob.browser.mfa import TwoFactorBrowser
from woob.exceptions import BrowserIncorrectPassword, BrowserUnavailable, OTPSentType, ScrapingBlocked, SentOTPQuestion

from .pages import (
    AccountPage,
    CallbackPage,
    DocumentDownloadPage,
    DocumentFilePage,
    DocumentPage,
    ForgottenPasswordPage,
    HomePage,
    LoginPage,
    MaintenancePage,
    OauthPage,
    ProfilePage,
    SendSMSPage,
    SubscriberPage,
    SubscriptionDetail,
    SubscriptionPage,
)


class MyURL(URL):
    def go(self, *args, **kwargs):
        kwargs["id_personne"] = self.browser.id_personne
        return super(MyURL, self).go(*args, **kwargs)


class BouyguesBrowser(TwoFactorBrowser):
    BASEURL = "https://api.bouyguestelecom.fr"

    home_page = URL(r"https://www.bouyguestelecom.fr/?$", HomePage)
    oauth_page = URL(r"https://oauth2.bouyguestelecom.fr/authorize", OauthPage)
    login_page = URL(r"https://www.mon-compte.bouyguestelecom.fr/cas/login", LoginPage)
    # used with oauth_page as a redirect_uri param
    callback = URL(
        r"https://assets.bouyguestelecom.fr/PICASSO-FRONT/main@0.19.1/bouyguestelecom.fr/callback.html",
        CallbackPage,
    )
    maintenance = URL(r"https://www.bouyguestelecom.fr/static/maintenance.html", MaintenancePage)
    forgotten_password_page = URL(
        r"https://www.mon-compte.bouyguestelecom.fr/mon-compte/mot-de-passe-oublie",
        r"https://www.bouyguestelecom.fr/mon-compte/mot-de-passe-oublie",
        ForgottenPasswordPage,
    )
    account_page = URL(r"https://www.bouyguestelecom.fr/mon-compte/?$", AccountPage)
    subscriber_page = MyURL(r"/personnes/(?P<id_personne>\d+)$", SubscriberPage)
    subscriptions_page = MyURL(r"/personnes/(?P<id_personne>\d+)/comptes-facturation", SubscriptionPage)
    subscription_detail_page = URL(r"/comptes-facturation/(?P<id_account>\d+)/contrats-payes", SubscriptionDetail)
    document_file_page = URL(r"/comptes-facturation/(?P<id_account>\d+)/factures/.*/documents/.*", DocumentFilePage)
    documents_page = URL(r"/graphql", DocumentPage)
    document_download_page = URL(r"/comptes-facturation/(?P<id_account>\d+)/factures/.*(\?|$)", DocumentDownloadPage)
    profile_page = MyURL(r"/personnes/(?P<id_personne>\d+)/coordonnees", ProfilePage)

    send_sms = URL(r"https://www.secure.bbox.bouyguestelecom.fr/services/SMSIHD/sendSMS.phtml", SendSMSPage)
    confirm_sms = URL(r"https://www.secure.bbox.bouyguestelecom.fr/services/SMSIHD/resultSendSMS.phtml")

    __states__ = ("execution", "otp_url", "access_token", "id_personne", "conversation_id")
    # We can do the login with session data only, and check if we require
    # interactive ourselves.
    HAS_CREDENTIALS_ONLY = True

    def __init__(self, config, username, password, lastname, *args, **kwargs):
        super(BouyguesBrowser, self).__init__(config, username, password, *args, **kwargs)
        self.lastname = lastname
        self.execution = None
        self.otp_url = None
        self.id_personne = None
        self.access_token = None
        self.contact = None
        self.conversation_id = None

        self.AUTHENTICATION_METHODS = {
            "otp_sms": self.handle_otp,
            "otp_email": self.handle_otp,
        }

    def set_session_data_from_current_url(self):
        fragments = dict(parse_qsl(urlparse(self.url).fragment))
        self.id_personne = jwt.get_unverified_claims(fragments["id_token"])["id_personne"]
        self.access_token = fragments["access_token"]
        authorization = "Bearer " + self.access_token
        self.session.headers["Authorization"] = authorization

    def build_oauth_param(self, redirect_uri, tmpl=True, client_id="ec.nav.bouyguestelecom.fr"):
        params = {
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "nonce": self.create_random_string(),
            "state": self.create_random_string(),
            "response_type": "id_token token",
        }
        if tmpl is True:
            params["tmpl"] = "bytelConnect"
        return params

    def login_with_session_data(self):
        # we can use session data to get a token and use it to login
        params = self.build_oauth_param(self.callback.urls[0])
        self.oauth_page.go(params=params)

        self.set_session_data_from_current_url()
        # we should go to account page to get cookies...
        self.account_page.go()
        # We can get one with more privileges on the same url but with
        # different parameters.
        params = self.build_oauth_param(self.account_page.build(), tmpl=False, client_id="a360.bouyguestelecom.fr")
        self.oauth_page.go(params=params)
        self.set_session_data_from_current_url()
        self.profile_page.go()

    def clear_init_cookies(self):
        # we need the cookies on the init_login
        # to try the login with session data
        pass

    def locate_browser(self, state):
        if self.config["otp_sms"].get() or self.config["otp_email"].get():
            # We have an sms value we don't want to go to the
            # last visited page (OTP page).
            return
        # set the acces token to the headers
        if self.access_token:
            self.session.headers["Authorization"] = "Bearer " + self.access_token

        if "url" in state and self.documents_page.match(state["url"]):
            # documents_page need a POST request and it's not like the result
            # will be used after locate_browser so it's better to keep it simple
            try:
                self.subscriptions_page.go()
            except ClientError as er:
                if er.response.status_code == 401 and "A valid Bearer token is required" in er.response.json().get(
                    "error_description"
                ):
                    # need to login again
                    return
                raise
        else:
            super(BouyguesBrowser, self).locate_browser(state)

    @staticmethod
    def create_random_string(n=32):
        chars = string.ascii_letters + string.digits
        rnd_str = ""
        for _ in range(n):
            rnd_str += chars[floor(random.random() * len(chars))]
        return rnd_str

    def init_login(self):
        try:
            self.login_with_session_data()
        except (ClientError, KeyError):
            self.home_page.go()
            try:
                params = self.build_oauth_param(self.callback.urls[0])
                self.oauth_page.go(params=params)

            except ClientError as e:
                if e.response.status_code == 407:
                    # The website systematically returns an HTTP 407 Proxy Authentication Required
                    # response when making this request from given IP addresses with a proxy.
                    # The same happens in Firefox when requesting from said IP addresses, and
                    # we have no such authentication to provide; we assume some kind of blocking
                    # might be in place, and consider it a ScrapingBlocked case.
                    raise ScrapingBlocked()
                raise

            if self.callback.is_here():
                self.handle_login_success_callback_page()
                return

            if self.maintenance.is_here():
                raise BrowserUnavailable()

            if not self.login_page.is_here():
                raise AssertionError("We should be on the login page.")
            # check for interactive login will send otp.
            self.check_interactive()
            try:
                self.page.login(self.username, self.password, self.lastname)
            except ClientError as e:
                if e.response.status_code == 401:
                    error = LoginPage(self, e.response).get_error_message()
                    raise BrowserIncorrectPassword(error)
                raise

            if self.callback.is_here():
                self.handle_login_success_callback_page()
                return

            if self.login_page.is_here():
                self.handle_otp_question()

            if self.forgotten_password_page.is_here():
                # when too much attempt has been done in a short time, bouygues redirect us here,
                # but no message is available on this page
                raise BrowserIncorrectPassword()

    def handle_login_success_callback_page(self):
        if self.page.has_id_and_access_token():
            self.set_session_data_from_current_url()
            # Mandatory to get full access to the pages needed to collect the data
            self.login_with_session_data()

            if not self.page.logged:
                raise AssertionError("We should be logged at this point")
        else:
            raise AssertionError("Unexpected redirection to callback page at login")

    def handle_otp_question(self):
        self.page.send_2fa_code()
        # This token is generated with js and will be needed in handle_otp to send the otp.
        self.execution = self.page.get_execution()
        # This URL will be needed to send the otp
        self.otp_url = self.page.url

        otp_question = {
            "medium_label": self.contact,
            "message": f"Saisir le code d'authentification. Code envoyé au: {self.contact}",
        }
        if not self.contact and re.match(r".+?@.+?", self.contact):
            otp_question["field_name"] = "otp_email"
            otp_question["medium_type"] = OTPSentType.EMAIL
        elif self.contact:
            otp_question["field_name"] = "otp_sms"
            otp_question["medium_type"] = OTPSentType.SMS

        if "medium_type" not in otp_question:
            raise AssertionError("Unexpected SCA method, neither sms nor email found")

        raise SentOTPQuestion(**otp_question)

    def handle_otp(self):
        try:
            self.location(
                self.otp_url,
                data={
                    "token": self.otp_sms or self.otp_email,
                    "_eventId_submit": "Envoyer",
                    "execution": self.execution,
                    "conversationId": self.conversation_id,
                    "geolocation": "",
                },
            )
        except ClientError as e:
            if e.response.status_code == 401:
                otp_data = LoginPage(self, e.response).get_otp_config()

                if otp_data["expired"] == "true":
                    raise BrowserIncorrectPassword(
                        "Code de vérification expiré. Pour votre sécurité, merci de générer un nouveau code."
                    )
                if int(otp_data["remaining_attempts"]) > 0:
                    raise BrowserIncorrectPassword(
                        f"Code erroné, Il vous reste {otp_data['remaining_attempts']} tentatives. Merci de réessayer"
                    )
                raise AssertionError(
                    f"Unidentified error on handle otp the max attempts ({otp_data['max_attempts']})"
                    + f" is reached , remaining_attempts : {otp_data['remaining_attempts']}."
                )
            raise

        self.location(
            self.otp_url,
            data={
                "execution": self.page.get_execution(),
                "_eventId_proceed": "",
                "conversationId": self.conversation_id,
                "geolocation": "",
            },
        )

        # after sending otp data we should get a token.
        self.handle_login_success_callback_page()

    @need_login
    def iter_subscriptions(self):
        subscriber = self.subscriber_page.go().get_subscriber()
        try:
            self.subscriptions_page.go()
        except ClientError as e:
            if e.response.status_code == 403 and not self.page.has_subscription_link():
                # the account has no subscriptions.
                return []
            raise
        for sub in self.page.iter_subscriptions():
            sub.subscriber = subscriber
            try:
                sub.label = self.subscription_detail_page.go(id_account=sub.id).get_label()
            except ClientError as e:
                if e.response.status_code == 403:
                    # Sometimes, subscription_detail_page is not available for a subscription.
                    # It's impossible to get the tel number associated with it and create a label with.
                    sub.label = sub.id
                else:
                    raise
            yield sub

    def request_invoices(self, invoice_number):
        with open(self.asset("invoices_query.txt"), "r") as rf:
            query = rf.read()

        payload = {
            "operationName": "GetInvoices",
            "variables": {
                "n": invoice_number,
                "personId": self.id_personne,
            },
            "query": query,
        }
        headers = {
            "Accept": "*/*",
            "Referer": "https://www.bouyguestelecom.fr/",
            "X-Graphql-Scope": "SWAP_CARE@0.0.46",
            "X-Process": "invoicesV8",
            "X-Source": "ACO",
        }
        self.documents_page.go(json=payload, headers=headers)

    @need_login
    def iter_documents(self, subscription):
        invoice_count = 0
        invoice_number_to_request = 0
        processed_docs = []
        # Set a limit to 1 invoice * 12 months * 50 years = 600 just in case since it's
        # not clear how many invoices there are per month
        while invoice_count == invoice_number_to_request and invoice_number_to_request <= 600:
            invoice_number_to_request += 10
            # Like the website request a number of invoices and increase the number
            # by 10 to get the next invoices
            self.request_invoices(invoice_number=invoice_number_to_request)
            for doc in self.page.iter_documents(subid=subscription.id):
                if doc.id in processed_docs:
                    # The invoices already handled are ignored
                    continue
                processed_docs.append(doc.id)
                yield doc

            invoice_count = self.page.get_invoice_count(subscription.id)
            if invoice_count > invoice_number_to_request:
                raise AssertionError("Unexpected invoice number, it shouldn't be higher than the number requested")

    @need_login
    def get_profile(self):
        self.profile_page.go()
        profile = self.page.get_profile()
        profile.id = self.id_personne
        if self.subscriber_page.go().is_company():
            self.page.fill_company_profile(obj=profile)
        else:
            self.page.fill_personal_profile(obj=profile)
        return profile

    @need_login
    def download_document(self, document):
        if document.url:
            download_page = self.open(document.url).page
            url = download_page.get_download_url()
            return self.open(url).content

    @need_login
    def post_message(self, receivers, content):
        self.send_sms.go()
        self.page.post_message(receivers, content)
        self.confirm_sms.open()  # no params: stateful?!
