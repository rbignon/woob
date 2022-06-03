# -*- coding: utf-8 -*-

# Copyright(C) 2019      Budget Insight
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

import string
import random
from math import floor
from urllib.parse import urlparse, parse_qsl

from jose import jwt

from woob.browser import URL, need_login
from woob.browser.browsers import TwoFactorBrowser
from woob.browser.exceptions import HTTPNotFound, ClientError
from woob.exceptions import BrowserIncorrectPassword, OTPSentType, ScrapingBlocked, SentOTPQuestion

from .pages import (
    LoginPage, ForgottenPasswordPage, SubscriberPage, SubscriptionPage, SubscriptionDetail, DocumentPage,
    DocumentDownloadPage, DocumentFilePage,
    SendSMSPage, ProfilePage, HomePage, AccountPage,
)


class MyURL(URL):
    def go(self, *args, **kwargs):
        kwargs['id_personne'] = self.browser.id_personne
        return super(MyURL, self).go(*args, **kwargs)


class BouyguesBrowser(TwoFactorBrowser):
    BASEURL = 'https://api.bouyguestelecom.fr'

    home_page = URL(r'https://www.bouyguestelecom.fr/?$', HomePage)
    oauth_page = URL(r'https://oauth2.bouyguestelecom.fr/authorize\?response_type=id_token token')
    login_page = URL(r'https://www.mon-compte.bouyguestelecom.fr/cas/login', LoginPage)
    forgotten_password_page = URL(
        r'https://www.mon-compte.bouyguestelecom.fr/mon-compte/mot-de-passe-oublie',
        r'https://www.bouyguestelecom.fr/mon-compte/mot-de-passe-oublie',
        ForgottenPasswordPage
    )
    account_page = URL(r'https://www.bouyguestelecom.fr/mon-compte/?$', AccountPage)
    subscriber_page = MyURL(r'/personnes/(?P<id_personne>\d+)$', SubscriberPage)
    subscriptions_page = MyURL(r'/personnes/(?P<id_personne>\d+)/comptes-facturation', SubscriptionPage)
    subscription_detail_page = URL(r'/comptes-facturation/(?P<id_account>\d+)/contrats-payes', SubscriptionDetail)
    document_file_page = URL(r'/comptes-facturation/(?P<id_account>\d+)/factures/.*/documents/.*', DocumentFilePage)
    documents_page = URL(r'/comptes-facturation/(?P<id_account>\d+)/factures(\?|$)', DocumentPage)
    document_download_page = URL(r'/comptes-facturation/(?P<id_account>\d+)/factures/.*(\?|$)', DocumentDownloadPage)
    profile_page = MyURL(r'/personnes/(?P<id_personne>\d+)/coordonnees', ProfilePage)

    send_sms = URL(r'https://www.secure.bbox.bouyguestelecom.fr/services/SMSIHD/sendSMS.phtml', SendSMSPage)
    confirm_sms = URL(r'https://www.secure.bbox.bouyguestelecom.fr/services/SMSIHD/resultSendSMS.phtml')

    __states__ = ('execution', 'otp_url', 'access_token', 'id_personne')
    # We can do the login with session data only, and check if we require
    # interactive ourselves.
    HAS_CREDENTIALS_ONLY = True

    def __init__(self, config, username, password, lastname, *args, **kwargs):
        super(BouyguesBrowser, self).__init__(config, username, password, *args, **kwargs)
        self.lastname = lastname

        self.AUTHENTICATION_METHODS = {
            'sms': self.handle_sms,
        }

    def set_session_data_from_current_url(self):
        fragments = dict(parse_qsl(urlparse(self.url).fragment))
        self.id_personne = jwt.get_unverified_claims(fragments['id_token'])['id_personne']
        self.access_token = fragments['access_token']
        authorization = 'Bearer ' + self.access_token
        self.session.headers['Authorization'] = authorization

    def login_with_session_data(self):
        # we can use session data to get a token and use it to login
        params = {
            'tmpl': 'bytelConnect',
            'redirect_uri': 'https://cdn.bouyguestelecom.fr/libs/auth/callback.html',
            'client_id': 'ec.nav.bouyguestelecom.fr',
            'nonce': self.create_random_string(),
            'state': self.create_random_string(),
        }
        self.oauth_page.go(params=params)

        self.set_session_data_from_current_url()
        # we should go to account page to get cookies...
        self.location('https://www.bouyguestelecom.fr/mon-compte')
        # We can get one with more privileges on the same url but with
        # different parameters.
        params = {
            'redirect_uri': 'https://www.bouyguestelecom.fr/mon-compte/',
            'client_id': 'a360.bouyguestelecom.fr',
            'nonce': self.create_random_string(),
            'state': self.create_random_string(),
        }

        self.oauth_page.go(params=params)
        self.set_session_data_from_current_url()
        self.profile_page.go()

    def clear_init_cookies(self):
        # we need the cookies on the init_login
        # to try the login with session data
        pass

    def locate_browser(self, state):
        if self.config['sms'].get():
            # We have an sms value we don't want to go to the
            # last visited page (SMS page).
            return
        # set the acces token to the headers
        if state.get('access_token'):
            self.session.headers['Authorization'] = 'Bearer ' + self.access_token
        super(BouyguesBrowser, self).locate_browser(state)

    @staticmethod
    def create_random_string():
        chars = string.ascii_letters + string.digits
        rnd_str = ''
        for _ in range(32):
            rnd_str += chars[floor(random.random() * len(chars))]
        return rnd_str

    def init_login(self):
        try:
            self.login_with_session_data()
        except (ClientError, KeyError):
            self.home_page.go()
            try:
                params = {
                    'tmpl': 'bytelConnect',
                    'redirect_uri': 'https://cdn.bouyguestelecom.fr/libs/auth/callback.html',
                    'client_id': 'ec.nav.bouyguestelecom.fr',
                    'nonce': self.create_random_string(),
                    'state': self.create_random_string(),
                }
                # This request redirects us to the login page
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

            if not self.login_page.is_here():
                raise AssertionError('We should be on the login page.')
            # check for interactive login will send otp.
            self.check_interactive()
            try:
                self.page.login(self.username, self.password, self.lastname)
            except ClientError as e:
                if e.response.status_code == 401:
                    error = LoginPage(self, e.response).get_error_message()
                    raise BrowserIncorrectPassword(error)
                raise
            otp_data = self.page.get_otp_config()
            self.execution = otp_data['execution']
            if self.login_page.is_here():
                if otp_data['is_sms'] == 'true':
                    self.otp_url = self.page.url
                    raise SentOTPQuestion(
                        'sms',
                        medium_type=OTPSentType.SMS,
                        medium_label=otp_data['phone'],
                        message=f"Saisir le code d'authentification, Code envoyé vers le :{otp_data['phone']}"
                    )
                raise AssertionError(f"Unexpected SCA method is_sms : {otp_data['is_sms']}")
            if self.forgotten_password_page.is_here():
                # when too much attempt has been done in a short time, bouygues redirect us here,
                # but no message is available on this page
                raise BrowserIncorrectPassword()

    def handle_sms(self):
        try:
            self.location(
                self.otp_url,
                data={
                    'token': self.sms,
                    '_eventId_submit': '',
                    'execution': self.execution,
                    'geolocation': ''
                }
            )
        except ClientError as e:
            if e.response.status_code == 401:
                otp_data = LoginPage(self, e.response).get_otp_config()

                if otp_data['is_sms'] != 'true':
                    raise AssertionError(f"Unidentified error on handle sms, is_sms : {otp_data['is_sms']}")
                if otp_data['expired'] == 'true':
                    raise BrowserIncorrectPassword(
                        'Code de vérification expiré. Pour votre sécurité, merci de générer un nouveau code.'
                    )
                if int(otp_data['remaining_attempts']) > 0:
                    raise BrowserIncorrectPassword(
                        f"Code SMS erroné, Il vous reste {otp_data['remaining_attempts']} tentatives. Merci de réessayer"
                    )
                raise AssertionError(
                    f"Unidentified error on handle sms the max attempts ({otp_data['max_attempts']}) is reached , remaining_attempts : {otp_data['remaining_attempts']}.")
            raise
        # after sending otp data we should get a token.
        execution = self.page.get_execution_code()
        self.location(self.url, data={'_eventId_proceed': '', 'execution': execution, 'geolocation': ''})
        self.set_session_data_from_current_url()
        self.login_with_session_data()

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

    @need_login
    def iter_documents(self, subscription):
        try:
            self.location(subscription.url)
        except HTTPNotFound as error:
            json_response = error.response.json()
            if json_response['error'] in ('facture_introuvable', 'compte_jamais_facture'):
                return []
            raise
        return self.page.iter_documents(subid=subscription.id)

    @need_login
    def get_profile(self):
        self.profile_page.go()
        profile = self.page.get_profile()
        profile.id = self.id_personne
        return profile

    @need_login
    def download_document(self, document):
        if document.url:
            # location to handle the page with document_download_page
            self.location(document.url)
            url = self.page.get_download_url()
            return self.open(url).content

    @need_login
    def post_message(self, receivers, content):
        self.send_sms.go()
        self.page.post_message(receivers, content)
        self.confirm_sms.open()  # no params: stateful?!
