# -*- coding: utf-8 -*-

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

from __future__ import unicode_literals


from woob.browser import LoginBrowser, StatesMixin, URL, need_login
from woob.exceptions import BrowserIncorrectPassword, BrowserQuestion, BrowserUnavailable
from woob.browser.exceptions import ClientError
from woob.tools.value import Value

from woob.capabilities.profile import Profile
from woob.capabilities.bill import Subscription, Bill

from datetime import datetime

class ScalewayBrowser(LoginBrowser, StatesMixin):
    BASEURL = 'https://api.scaleway.com'
    TIMEOUT = 60

    login = URL(r'/account/v1/jwt')
    profile = URL(r'/account/v1/users/(?P<idAccount>*)')
    invoices = URL(r'/billing/v1/invoices\?page=1&per_page=10&organization_id=(?P<idOrganization>*)')

    __states__ = ('jwtkey', 'jwtrenew', 'idaccount', 'idorganisation')

    def __init__(self, config, *args, **kwargs):
        self.config = config
        kwargs['username'] = self.config['login'].get()
        kwargs['password'] = self.config['password'].get()
        super(ScalewayBrowser, self).__init__(*args, **kwargs)
        self.jwtkey = ''
        self.jwtrenew = ''
        self.idaccount = ''
        self.idorganisation = ''

    def do_login(self):
        if not self.jwtkey:
            try:
                if self.config['otp'].get():
                    self.login.go(method="POST", json={"email":self.username,"password":self.password,"renewable":True,"2FA_token":self.config['otp'].get()})
                else:
                    self.login.go(method="POST", json={"email":self.username,"password":self.password,"renewable":True})
            except ClientError as e:
                if e.response.status_code == 401:
                    raise BrowserIncorrectPassword()
                if e.response.status_code == 403:
                    if not self.config['otp'].get():
                        raise BrowserQuestion(Value('otp', label='Entrer votre code OTP (2FA)'))
                    raise
                raise

            try:
                result = self.response.json()
                self.jwtkey = result["auth"]["jwt_key"]
                self.jwtrenew = result["auth"]["jwt_renew"]
                self.idaccount = result["jwt"]["audience"]
                self.idorganisation = result["jwt"]["organization_id"]
            except:
                raise BrowserUnavailable()

    @need_login
    def get_profile(self):
        self.session.headers['x-session-token'] = "%s" % self.jwtkey
        self.profile.go(idAccount=self.idaccount)
        result = self.response.json()
        pr = Profile()
        pr.name = result["user"]["fullname"]
        pr.phone = result["user"]["phone_number"]
        pr.country = result["user"]["locale"]
        pr.email = result["user"]["email"]
        return pr

    @need_login
    def get_subscription_list(self):
        self.session.headers['x-session-token'] = "%s" % self.jwtkey
        self.profile.go(idAccount=self.idaccount)
        result = self.response.json()
        sub = Subscription()
        sub.id = result["user"]["organizations"][0]["id"]
        sub.subscriber = sub.label = result["user"]["organizations"][0]["name"]
        return sub

    @need_login
    def iter_documents(self, subscription=''):
        self.session.headers['x-session-token'] = "%s" % self.jwtkey
        if subscription == '':
            subscription = self.idorganisation
        self.invoices.go(idOrganization=subscription)
        result = self.response.json()
        invoices = []
        for invoice in result['invoices']:
            bouleEt = Bill()
            bouleEt.currency = invoice["currency"]
            bouleEt.startdate = datetime.strptime(invoice["start_date"], '%Y-%m-%dT%H:%M:%S+00:00')
            bouleEt.finishdate = datetime.strptime(invoice["stop_date"], '%Y-%m-%dT%H:%M:%S.%f+00:00')
            bouleEt.duedate = datetime.strptime(invoice["due_date"], '%Y-%m-%dT%H:%M:%S.%f+00:00')
            bouleEt.date = datetime.strptime(invoice["issued_date"], '%Y-%m-%dT%H:%M:%S.%f+00:00')
            bouleEt.id = invoice["id"]
            bouleEt.total_price = invoice["total_taxed"]
            bouleEt.pre_tax_price = invoice["total_untaxed"]
            startdate_str = invoice["start_date"]
            bouleEt.url = f"https://api.scaleway.com/billing/v1/invoices/{subscription}/{startdate_str}/{bouleEt.id}/?format=pdf"
            invoices.append(bouleEt)
        return invoices

    @need_login
    def download_document(self, document):
        self.session.headers['x-session-token'] = "%s" % self.jwtkey
        return self.open(document.url).content
