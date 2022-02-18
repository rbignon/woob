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

from woob.browser import LoginBrowser, URL, need_login
from woob.browser.exceptions import HTTPNotFound, ClientError
from woob.exceptions import BrowserIncorrectPassword, ScrapingBlocked

from .pages import (
    LoginPage, ForgottenPasswordPage, SubscriberPage, SubscriptionPage, SubscriptionDetail, DocumentPage,
    DocumentDownloadPage, DocumentFilePage,
    SendSMSPage, ProfilePage, HomePage, AccountPage,
)


class MyURL(URL):
    def go(self, *args, **kwargs):
        kwargs['id_personne'] = self.browser.id_personne
        kwargs['headers'] = self.browser.headers
        return super(MyURL, self).go(*args, **kwargs)


class BouyguesBrowser(LoginBrowser):
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

    def __init__(self, username, password, lastname, *args, **kwargs):
        super(BouyguesBrowser, self).__init__(username, password, *args, **kwargs)
        self.lastname = lastname
        self.id_personne = None
        self.headers = None

    @staticmethod
    def create_random_string():
        chars = string.ascii_letters + string.digits
        rnd_str = ''
        for _ in range(32):
            rnd_str += chars[floor(random.random() * len(chars))]
        return rnd_str

    def do_login(self):
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
                raise ScrapingBlocked()
            raise

        if not self.login_page.is_here():
            raise AssertionError('We should be on the login page.')

        try:
            self.page.login(self.username, self.password, self.lastname)
        except ClientError as e:
            if e.response.status_code == 401:
                error = LoginPage(self, e.response).get_error_message()
                raise BrowserIncorrectPassword(error)
            raise

        if self.forgotten_password_page.is_here():
            # when too much attempt has been done in a short time, bouygues redirect us here,
            # but no message is available on this page
            raise BrowserIncorrectPassword()

        self.account_page.go()

        params = {
            'redirect_uri': 'https://www.bouyguestelecom.fr/mon-compte/',
            'client_id': self.page.get_client_id(),
            'nonce': self.create_random_string(),
            'state': self.create_random_string(),
        }
        self.oauth_page.go(params=params)
        fragments = dict(parse_qsl(urlparse(self.url).fragment))

        self.id_personne = jwt.get_unverified_claims(fragments['id_token'])['id_personne']
        authorization = 'Bearer ' + fragments['access_token']
        self.headers = {'Authorization': authorization}

    @need_login
    def iter_subscriptions(self):
        subscriber = self.subscriber_page.go().get_subscriber()
        self.subscriptions_page.go()
        for sub in self.page.iter_subscriptions():
            sub.subscriber = subscriber
            try:
                sub.label = self.subscription_detail_page.go(id_account=sub.id, headers=self.headers).get_label()
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
            self.location(subscription.url, headers=self.headers)
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
            return self.location(document.url, headers=self.headers).content

    @need_login
    def post_message(self, receivers, content):
        self.send_sms.go()
        self.page.post_message(receivers, content)
        self.confirm_sms.open()  # no params: stateful?!
