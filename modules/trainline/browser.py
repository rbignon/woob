# -*- coding: utf-8 -*-

# Copyright(C) 2016      Edouard Lambert
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

from requests import ReadTimeout

from woob.browser import URL
from woob.browser.browsers import LoginBrowser, need_login
from woob.exceptions import BrowserIncorrectPassword
from woob.browser.exceptions import ClientError
from woob.tools.antibot.akamai import AkamaiMixin
from woob.tools.decorators import retry

from .pages import HomePage, SigninPage, UserPage, DocumentsPage


class TrainlineBrowser(LoginBrowser, AkamaiMixin):
    BASEURL = 'https://www.thetrainline.com'

    home = URL(r'/$', HomePage)
    signin = URL(r'/login-service/api/login', SigninPage)
    user_page = URL(r'/login-service/v5/user', UserPage)
    documents_page = URL(r'/my-account/api/bookings/past', DocumentsPage)

    @retry(ReadTimeout)
    def do_login(self):
        # set some cookies
        self.go_home()

        # set X-Requested-With AFTER go_home(), to get the akamai url in html
        # else it is missing
        # this url is used by AkamaiMixin to resolve challenge
        self.session.headers['X-Requested-With'] = 'XMLHttpRequest'

        if self.session.cookies.get('_abck'):
            akamai_url = self.page.get_akamai_url()
            if akamai_url:
                # because sometimes this url is missing
                # in that case, we simply don't resolve challenge
                akamai_solver = self.get_akamai_solver(akamai_url, self.url)
                akamai_solver.html_doc = self.page.doc
                cookie_abck = self.session.cookies['_abck']
                self.post_sensor_data(akamai_solver, cookie_abck)

        try:
            self.signin.go(json={'email': self.username, 'password': self.password})
        except ClientError as e:
            if e.response.status_code in (400, 403):
                error = e.response.json().get('message')
                if 'invalid_grant' in error:
                    raise BrowserIncorrectPassword(error)
            raise

        self.user_page.go()

    @need_login
    def get_subscription_list(self):
        self.user_page.stay_or_go()
        yield self.page.get_subscription()

    @need_login
    def iter_documents(self, subscription):
        self.documents_page.go()
        return self.page.iter_documents(subid=subscription.id)
