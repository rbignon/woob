# -*- coding: utf-8 -*-

# Copyright(C) 2017      Vincent A

# flake8: compatible

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

from woob.browser import LoginBrowser, URL, need_login
from woob.browser.exceptions import ServerError
from woob.exceptions import BrowserIncorrectPassword, BrowserQuestion
from woob.tools.value import Value

from .pages import LoginPage, SubscriptionsPage, DocumentsPage


class InfomaniakBrowser(LoginBrowser):
    BASEURL = 'https://manager.infomaniak.com'

    login = URL(r'https://login.infomaniak.com/api/login', LoginPage)
    profile = URL(r'/v3/api/proxypass/profile', SubscriptionsPage)
    documents = URL(r'/v3/api/invoicing/(?P<subid>.*)/invoices', DocumentsPage)

    def __init__(self, config, *args, **kwargs):
        self.config = config
        kwargs['username'] = self.config['login'].get()
        kwargs['password'] = self.config['password'].get()
        super(InfomaniakBrowser, self).__init__(*args, **kwargs)

    def do_login(self):
        try:
            if self.config['otp'].get():
                self.login.go(
                    data={
                        'login': self.username,
                        'password': self.password,
                        'double_auth_code': self.config['otp'].get(),
                    }
                )
            else:
                self.login.go(data={'login': self.username, 'password': self.password})
        except ServerError as e:
            if e.response.status_code == 500:
                page = LoginPage(self, e.response)
                # first for the wrongpass, second for the otp failed
                error_msgs = ["Invalid login or password", "The authentication code is incorrect"]
                if page.get_error() in error_msgs:
                    raise BrowserIncorrectPassword(page.get_error())
            raise

        if self.page.has_otp and not self.config['otp'].get():
            raise BrowserQuestion(Value('otp', label='Enter the OTP'))

    @need_login
    def iter_subscription(self):
        self.profile.go()
        return [self.page.get_subscription()]

    @need_login
    def iter_documents(self, subscription):
        params = {
            'ajax': 'true',
            'order_by': 'name',
            'order_for[name]': 'asc',
            'page': '1',
            'per_page': '100',
        }
        self.documents.go(subid=subscription.id, params=params)
        return self.page.iter_documents(subid=subscription.id)
