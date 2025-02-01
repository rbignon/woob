# -*- coding: utf-8 -*-

# Copyright(C) 2012-2022  Budget Insight
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

from woob.browser import URL, LoginBrowser, StatesMixin, need_login
from woob.browser.exceptions import ClientError
from woob.exceptions import ActionNeeded, BrowserIncorrectPassword

from .pages import DocumentsPage, LoginPage, ProfilePage


class DeliverooBrowser(LoginBrowser, StatesMixin):
    BASEURL = "https://deliveroo.fr"

    login = URL(r"/fr/login", LoginPage)
    profile = URL(r"/fr/account$", ProfilePage)
    documents = URL(r"https://consumer-ow-api.deliveroo.com/orderapp/v1/users/(?P<subid>.*)/orders", DocumentsPage)

    def do_login(self):
        # clear cookies to avoid 307 on login request
        self.session.cookies.clear()

        # get some cookies, 'locale', 'roo_guid'... if we don't have this we have an error 403
        self.go_home()
        self.login.go()
        csrf_token = self.page.get_csrf_token()
        verif_email = {
            "email_address": self.username,
        }

        response_validity_email = self.open(
            "https://consumer-ow-api.deliveroo.com/orderapp/v1/check-email",
            json=verif_email,
            headers={"x-csrf-token": csrf_token},
        )

        if response_validity_email.json().get("registered") is False:
            raise BrowserIncorrectPassword("The account does not exist")

        try:
            self.location(
                "/fr/auth/login",
                json={"email": self.username, "password": self.password},
                headers={"x-csrf-token": csrf_token},
            )
        except ClientError as error:
            # if the status_code is 423, the user must change their password
            if error.response.status_code == 423:
                raise ActionNeeded(error.response.json().get("msg"))
            elif error.response.status_code == 401:
                raise BrowserIncorrectPassword(error.response.json().get("msg"))
            raise

    @need_login
    def get_subscription_list(self):
        self.profile.stay_or_go()
        assert self.profile.is_here()
        yield self.page.get_item()

    @need_login
    def iter_documents(self, subscription):
        headers = {"authorization": "Bearer %s" % self.session.cookies["consumer_auth_token"]}
        self.documents.go(subid=subscription.id, params={"limit": 25, "offset": 0}, headers=headers)
        assert self.documents.is_here()

        return self.page.get_documents(subid=subscription.id, baseurl=self.BASEURL)
