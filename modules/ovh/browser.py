# -*- coding: utf-8 -*-

# Copyright(C) 2015      Vincent Paredes
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

import time
from requests.exceptions import HTTPError, TooManyRedirects, ConnectionError
from datetime import datetime, timedelta

from woob.browser import LoginBrowser, URL, need_login, StatesMixin
from woob.exceptions import BrowserIncorrectPassword, BrowserQuestion, BrowserUnavailable
from woob.tools.capabilities.bill.documents import merge_iterators
from woob.tools.value import Value
from woob.tools.decorators import retry

from .pages import LoginPage, ProfilePage, BillsPage, RefundsPage


class OvhBrowser(LoginBrowser, StatesMixin):
    BASEURL = 'https://www.ovh.com'

    login = URL(
        r'/auth/',
        r'/manager/',
        LoginPage,
    )
    profile = URL(r'/engine/api/me', ProfilePage)
    documents = URL(
        r'/engine/2api/sws/billing/bills\?count=0&date=(?P<fromDate>.*)&dateTo=(?P<toDate>.*)&offset=0',
        BillsPage
    )
    refunds_documents = URL(
        r'/engine/2api/sws/billing/refunds\?count=0&date=(?P<fromDate>.*)&dateTo=(?P<toDate>.*)&offset=0',
        RefundsPage
    )

    __states__ = ('otp_form', 'otp_url')
    STATE_DURATION = 10

    otp_form = None
    otp_url = None

    def __init__(self, config=None, *args, **kwargs):
        self.config = config
        kwargs['username'] = self.config['login'].get()
        kwargs['password'] = self.config['password'].get()
        super(OvhBrowser, self).__init__(*args, **kwargs)

    def locate_browser(self, state):
        # Add Referer to avoid 401 response code when call url for the second time
        try:
            self.location(state['url'], headers={'Referer': self.absurl('/manager/dedicated/index.html')})
        except (HTTPError, TooManyRedirects):
            pass

    def validate_security_form(self):
        res_form = self.otp_form
        res_form['emailCode'] = self.config['pin_code'].get()

        self.location(self.url, data=res_form)

    @retry(BrowserUnavailable)
    def do_login(self):
        if self.config['pin_code'].get():
            self.validate_security_form()

            if not self.page.is_logged():
                raise BrowserIncorrectPassword("Login / Password or authentication pin_code incorrect")
            return

        try:
            self.login.go()
        except ConnectionError as e:
            raise BrowserUnavailable(e)

        if self.page.is_logged():
            return

        self.page.login(self.username, self.password)

        if self.page.check_website_double_auth():
            self.otp_form = self.page.get_security_form()
            self.otp_url = self.url

            raise BrowserQuestion(Value('pin_code', label=self.page.get_otp_message() or 'Please type the OTP you received'))

        if self.page.check_user_double_auth():
            _2fa_type = self.config['2fa_type'].get()
            if _2fa_type is None:
                raise BrowserQuestion(Value('2fa_type', label="Double factor authentication is active. Please choose the mechanism ('totp', 'sms', 'u2f', 'staticOTP'). (You may need to configure '2fa_type' in the config file to skip this question)."))
            self.page.maybe_switch_user_double_auth(_2fa_type)

            _2fa_value = self.config['2fa_value'].get()
            if _2fa_value is None:
                raise BrowserQuestion(Value('2fa_value', label="Double factor authentication is active. Please enter the value (You may configure '2fa_value'  in the config file if you want to skip this question."))
            self.page.submit_user_double_auth(_2fa_type, _2fa_value)

        self.login.go()
        if not self.page.is_logged():
            raise BrowserIncorrectPassword(self.page.get_error_message())

    @need_login
    def get_subscription_list(self):
        self.profile.stay_or_go()
        return self.page.get_subscriptions()

    @need_login
    def iter_documents(self, subscription):
        from_date = (datetime.now() - timedelta(days=2 * 365)).strftime("%Y-%m-%dT00:00:00Z")
        to_date = time.strftime("%Y-%m-%dT%H:%M:%S.999Z")
        self.documents.stay_or_go(
            fromDate=from_date,
            toDate=to_date,
        )
        documents = self.page.get_documents(subid=subscription.id)
        self.refunds_documents.go(
            fromDate=from_date,
            toDate=to_date,
        )
        refunds_documents = self.page.get_documents(subid=subscription.id)
        return merge_iterators(documents, refunds_documents)
