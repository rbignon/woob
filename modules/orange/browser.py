# -*- coding: utf-8 -*-

# Copyright(C) 2012-2014 Vincent Paredes
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

from __future__ import unicode_literals

import random
from time import sleep

from requests.exceptions import ConnectTimeout

from woob.browser import LoginBrowser, URL, need_login, StatesMixin
from woob.capabilities import NotAvailable
from woob.capabilities.bill import Subscription
from woob.exceptions import (
    BrowserIncorrectPassword, BrowserUnavailable, ActionNeeded, BrowserPasswordExpired,
    ScrapingBlocked,
)
from woob.browser.exceptions import ClientError, HTTPNotFound, ServerError
from woob.tools.decorators import retry

from .pages import LoginPage
from .pages.captcha import OrangeCaptchaHandler, CaptchaPage
from .pages.login import ManageCGI, HomePage, PasswordPage, PortalPage
from .pages.bills import (
    SubscriptionsPage, SubscriptionsApiPage, BillsApiProPage, BillsApiParPage,
    BillsApiProRechargeablePage, ContractsPage, ContractsApiPage,
)
from .pages.profile import ProfileParPage, ProfileApiParPage, ProfileProPage


__all__ = ['OrangeBillBrowser']


class RetryOnCaptcha(Exception):
    pass


class OrangeBillBrowser(LoginBrowser, StatesMixin):
    TIMEOUT = 60

    STATE_DURATION = 20

    BASEURL = 'https://espaceclientv3.orange.fr'

    home_page = URL(r'https://businesslounge.orange.fr/?$', HomePage)
    portal_page = URL(r'https://www.orange.fr/portail', PortalPage)
    login_page = URL(
        r'https://login.orange.fr/\?service=sosh&return_url=https://www.sosh.fr/',
        r'https://login.orange.fr/$',
        LoginPage,
    )
    login_api = URL(r'https://login.orange.fr/api/login')
    password_page = URL(r'https://login.orange.fr/api/password', PasswordPage)
    captcha_page = URL(r'https://login.orange.fr/captcha', CaptchaPage)

    contracts = URL(r'https://espaceclientpro.orange.fr/api/contracts', ContractsPage)
    contracts_api = URL(
        r'https://espace-client.orange.fr/ecd_wp/portfoliomanager/contracts/users/current\?filter=telco,security',
        ContractsApiPage
    )

    subscriptions = URL(
        r'https://espaceclientv3.orange.fr/js/necfe.php\?zonetype=bandeau&idPage=gt-home-page',
        SubscriptionsPage
    )
    subscriptions_api = URL(
        r'https://sso-f.orange.fr/omoi_erb/portfoliomanager/v2.0/contractSelector/users/current',
        SubscriptionsApiPage
    )

    manage_cgi = URL(r'https://eui.orange.fr/manage_eui/bin/manage.cgi', ManageCGI)

    bills_api_pro = URL(
        r'https://espaceclientpro.orange.fr/api/contract/(?P<subid>\d+)/bills\?count=(?P<count>)',
        BillsApiProPage,
    )

    bills_api_pro_rechargeable = URL(
        r'https://businesslounge.orange.fr/api/api/3.0.0/ecu/retrieve_bill.json',
        BillsApiProRechargeablePage,
    )

    bills_api_par = URL(
        r'https://espace-client.orange.fr/ecd_wp/facture/v2.0/billsAndPaymentInfos/users/current/contracts/(?P<subid>\d+)',
        BillsApiParPage
    )
    doc_api_par = URL(r'https://espace-client.orange.fr/ecd_wp/facture/v1.0/pdf')

    doc_api_pro = URL(r'https://espaceclientpro.orange.fr/api/contract/(?P<subid>\d+)/bill/(?P<dir>.*)/(?P<fact_type>.*)/\?(?P<billparams>)')
    profile_par = URL(r'/\?page=profil-infosPerso', ProfileParPage)
    profile_api_par = URL(r'https://espace-client.orange.fr/ecd_wp/account/identification', ProfileApiParPage)
    profile_pro = URL(r'https://businesslounge.orange.fr/profil', ProfileProPage)

    def __init__(self, specific_header, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if specific_header:
            key, value = specific_header.split(':')
            self.session.headers[key] = value

    def locate_browser(self, state):
        # If a pro is logged by going to portal_page we will be redirected to home_page
        self.portal_page.go()
        if not self.home_page.is_here():
            # If a par is connected by going to profile_par, we will not be redirected
            headers = {
                'x-orange-caller-id': 'ECQ',
                'accept': 'application/vnd.mason+json',
            }
            self.profile_api_par.go(headers=headers)

    @retry(RetryOnCaptcha, tries=2)
    def go_on_login_page(self):
        """ Little hack here.
        Retrying on this requests if encounter a captcha allow us to bypass
        completely said captcha and Datadome challenge.
        We receive in the response of the first request a "trust" cookie and a "datadome"
        cookie without solving anything.
        Simply retrying while carrying those cookies bypass completely Orange antibot safety
        """
        self.login_page.go()
        if self.page.has_captcha():
            raise RetryOnCaptcha()

    def do_login(self):
        assert isinstance(self.username, str)
        assert isinstance(self.password, str)
        try:
            try:
                self.go_on_login_page()
            except RetryOnCaptcha:
                pass
            if self.page.has_captcha():
                # If captcha still here after retrying, we need to solve it
                self._handle_captcha()

            json_data = {
                'login': self.username,
                'params': {
                    'return_url': 'https://espace-client.orange.fr/page-accueil',
                },
            }
            self.login_api.go(json=json_data)

            json_data = {
                'password': self.password,
                'remember': False,
            }
            self.password_page.go(json=json_data)
            error_message = self.page.get_change_password_message()
            if error_message:
                raise BrowserPasswordExpired(error_message)

            self.portal_page.go()

        except ClientError as error:
            if error.response.status_code == 401:
                raise BrowserIncorrectPassword(error.response.json().get('message', ''))
            if error.response.status_code == 403:
                if error.response.headers['Content-Type'] == 'text/html':
                    # When we are blocked, the error page is in html
                    if 'Cette page ne vous est pas accessible' in error.response.text:
                        raise ScrapingBlocked()
                    raise AssertionError('Unhandled html error page at login')
                else:
                    # occur when user try several times with a bad password, orange block his account for a short time
                    raise BrowserIncorrectPassword(error.response.json())
            raise

    def get_nb_remaining_free_sms(self):
        raise NotImplementedError()

    def post_message(self, message, sender):
        raise NotImplementedError()

    def _handle_captcha(self):
        data_captcha = self.page.get_captcha_data()

        if not data_captcha:
            raise BrowserUnavailable()

        images = self.page.download_images(data_captcha)
        # captcha resolution takes about 50 milliseconds
        self.captcha_handler = OrangeCaptchaHandler(self.logger, data_captcha['indications'], images)
        captcha_response = self.captcha_handler.get_captcha_response()

        # we need to wait a little bit, because we are human after all^^
        waiting = random.randint(5000, 9000) / 1000
        sleep(waiting)
        body = {'value': captcha_response}
        self.location('https://login.orange.fr/front/captcha', json=body)

    def _iter_subscriptions_by_type(self, name, _type):
        self.location('https://espaceclientv3.orange.fr/?page=gt-home-page&%s' % _type)
        self.subscriptions.go()
        for sub in self.page.iter_subscription():
            sub.subscriber = name
            yield sub

    @retry(BrowserUnavailable, tries=2, delay=10)
    @need_login
    def get_subscription_list(self):
        try:
            # look at the type of account, pro or par and associates the right profile page
            self.portal_page.go()
            if self.home_page.is_here():
                self.profile_pro.go()
            else:
                headers = {
                    'x-orange-caller-id': 'ECQ',
                    'accept': 'application/vnd.mason+json',
                }
                self.profile_api_par.go(headers=headers)

            # we land on manage_cgi page when there is cgu to validate
            if self.manage_cgi.is_here():
                # but they are not in this page, we have to go to home_page to get message
                self.home_page.go()
                msg = self.page.get_error_message()
                assert "Nos Conditions Générales d'Utilisation ont évolué" in msg, msg
                raise ActionNeeded(msg)
            else:
                profile = self.page.get_profile()
                if profile._subscriber:
                    subscriber = profile._subscriber
                else:
                    subscriber = self.page.get_name()
        except ConnectTimeout:
            # sometimes server just doesn't answer
            raise BrowserUnavailable()

        # this only works when there are pro subs.
        nb_sub = 0
        subscription_id_list = []
        api_subscription_id_list = []  # for logging only
        if not subscriber:
            self.profile_par.go()
            if self.profile_par.is_here():
                subscriber = self.page.get_subscriber()

        subscriptions = {}
        try:
            params = {
                'page': 1,
                'nbcontractsbypage': 15,
            }
            self.contracts.go(params=params)
            for sub in self.page.iter_subscriptions():
                # subscriber may be empty on some connection
                # store subscription for now and get subscriber later if it's the case
                sub.subscriber = subscriber
                subscriptions[sub.id] = sub
                subscription_id_list.append(sub.id)
            nb_sub = self.page.doc['totalContracts']
        except (ServerError, HTTPNotFound):
            pass

        try:
            headers = {
                "Accept": "application/json;version=1",
                "X-Orange-Caller-Id": "ECQ",
                "X-Orange-Origin-ID": "ECQ",
            }
            for sub in self.contracts_api.go(headers=headers).iter_subscriptions():
                # subscription returned here may be duplicated with the one returned by contracts page
                api_subscription_id_list.append(sub.id)
                if sub.id not in subscriptions.keys():
                    subscriptions[sub.id] = sub
                    nb_sub += 1
                elif subscriptions[sub.id].subscriber is NotAvailable:
                    # because sometimes subscriber is only available on contracts page
                    # sometimes just in contracts_api
                    # sometimes in both page, (but it's not always the same)
                    # sometimes it's just not available
                    subscriptions[sub.id].subscriber = sub.subscriber

        except (ServerError, ClientError) as e:
            # The orange website will return odd status codes when there are no subscriptions to return
            # I've seen the 404, 500 and 503 response codes
            # In a well designed website, it should be just a 204.
            if e.response.status_code not in (404, 500, 503):
                raise

        # Make a fake subscription if the user has a rechargeable mobile
        try:
            # Raises a 401 error if the current user is not concerned
            self.bills_api_pro_rechargeable.go()

            subscription = Subscription()
            subscription.id = self.username
            subscription.label = 'Forfait rechargeable Orange Business Lounge'
            subscription.subscriber = subscriber
            subscription._is_pro = True

            subscriptions[subscription.id] = subscription
            subscription_id_list.append(subscription.id)
            api_subscription_id_list.append(subscription.id)
            nb_sub += 1
        except ClientError as e:
            # Error 401 is expected if the user does not have a rechargeable
            # subscription, if other error code is returned, raise it
            if not e.response.status_code == 401:
                raise

        for sub in subscriptions.values():
            yield sub

        # for logging purpose only
        for subid in subscription_id_list:
            if subid not in api_subscription_id_list:
                # there is a subscription which is returned by contracts page and not by contracts_api
                # we can't get rid of contracts page
                # PS: still True for some connections on 2022-10-05
                self.logger.warning(
                    'there is a subscription which is returned by contracts page and not by contracts_api'
                )

        if nb_sub > 0:
            return
        # if nb_sub is 0, we continue, because we can get them in next url

        for sub in self._iter_subscriptions_by_type(profile.name, 'sosh'):
            nb_sub += 1
            yield sub
        for sub in self._iter_subscriptions_by_type(profile.name, 'orange'):
            nb_sub += 1
            yield sub

        if nb_sub == 0:
            # No subscriptions found, trying with the API.
            # TODO: this part may be deprecated, remove it if it's not used anymore
            self.logger.warning('no subscription found, try with subscriptions_api URL')
            headers = {
                'X-Orange-Caller-Id': 'ECQ',
            }
            self.subscriptions_api.go(headers=headers)
            for sub in self.page.iter_subscription():
                sub.subscriber = profile.name
                yield sub

    @need_login
    def iter_documents(self, subscription):
        documents = []
        if subscription._is_pro:
            for d in self.bills_api_pro.go(subid=subscription.id, count=72).get_bills(subid=subscription.id):
                documents.append(d)
            # check pagination for this subscription
            assert len(documents) != 73

            try:
                self.bills_api_pro_rechargeable.go()
            except ClientError as e:
                # User has no rechargeable subscription, 401 response and blank page
                if e.response.status_code != 401 or e.response.text:
                    raise
            else:
                # Retrieve bills from rechargeable subscription
                for bill in self.bills_api_pro_rechargeable.go().get_bills(subid=subscription.id):
                    documents.append(bill)

                    # TODO I could not find account with downloadable documents (i. e. account manager
                    # or CEO of the company) so the case where the user wants to download these documents
                    # is currently not handled properly (I mean I have no guarantee it will work).
                    # Do not hesitate to remove the conditional block with its logger below once you
                    # find one and fix what needs to be fixed
                    if bill._download_link:
                        self.logger.warning(
                            'The bill %s has a specified URL (unhandled case, pay attention ' % bill.id
                            + 'when you are trying to download it). URL: %s' % bill._download_link
                        )

        else:
            headers = {'x-orange-caller-id': 'ECQ'}
            try:
                self.bills_api_par.go(subid=subscription.id, headers=headers)
            except ServerError as e:
                if e.response.status_code in (503, ):
                    self.logger.info("Server Error : %d" % e.response.status_code)
                    return []
                raise

            except ClientError as e:
                if e.response.status_code == 412:
                    # if the code is 412 the user is not the owner of the subscription and we can't get the invoices
                    msg = e.response.json()['error']['customerMessage']['subMessage']
                    self.logger.info("no documents because: %s", msg)
                    return []
                raise

            for b in self.page.get_bills(subid=subscription.id):
                documents.append(b)
        return iter(documents)

    @need_login
    def get_profile(self):
        headers = {
            'x-orange-caller-id': 'ECQ',
            'accept': 'application/vnd.mason+json',
        }
        self.profile_api_par.go(headers=headers)
        if not self.profile_api_par.is_here():
            self.profile_pro.go()
        return self.page.get_profile()

    @retry(ServerError, delay=10)
    @need_login
    def download_document(self, document):
        # sometimes the site sends us a server error when downloading the document.
        # it is necessary to try again.
        try:
            if document._is_v2:
                # get 404 without this header
                return self.open(document.url, headers={'x-orange-caller-id': 'ECQ'}).content
            return self.open(document.url).content
        except ClientError as e:
            if e.response.status_code == 422:
                # if the code is 422 the download of the document is currently unavailable
                return NotAvailable
            raise
