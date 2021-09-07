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


from woob.browser import LoginBrowser, URL, need_login
from woob.exceptions import BrowserIncorrectPassword
from woob.browser.exceptions import ClientError

from .pages import LoginPage, ProfilePage, DocumentsPage


class OnlinenetBrowser(LoginBrowser):
    BASEURL = 'https://console.online.net/en/'
    TIMEOUT = 60

    login = URL('login', LoginPage)
    profile = URL('account/edit', ProfilePage)
    documents = URL('bill/list', DocumentsPage)

    def do_login(self):
        self.login.go()

        try:
            self.page.login(self.username, self.password)
        except ClientError as e:
            if e.response.status_code == 401:
                error_msg = LoginPage(self, e.response).get_error()
                raise BrowserIncorrectPassword(error_msg)
            raise

    @need_login
    def get_subscription_list(self):
        return self.profile.stay_or_go().get_list()

    @need_login
    def iter_documents(self, subscription):
        for b in self.documents.stay_or_go().get_bills():
            yield b
        for d in self.documents.stay_or_go().get_documents():
            yield d
