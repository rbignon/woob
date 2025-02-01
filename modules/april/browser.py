# Copyright(C) 2020      Ludovic LANGE
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

from datetime import date
from urllib.parse import parse_qs, urlparse

import requests

from woob.browser import URL, LoginBrowser, OAuth2Mixin, need_login
from woob.browser.exceptions import BrowserTooManyRequests, ClientError
from woob.capabilities.base import NotAvailable
from woob.capabilities.bill import Subscription
from woob.exceptions import BrowserIncorrectPassword

from .pages import DocumentsPage, HomePage, LoginPage, ProfilePage


class AprilBrowser(OAuth2Mixin, LoginBrowser):
    BASEURL = "https://api-gateway.april.fr/"
    ACCESS_TOKEN_URI = "https://am-gateway.april.fr/selfcare/oauth/token"
    client_id = "se_selfcare_spi"

    profile = URL(r"/selfcare/personne/informations$", ProfilePage)
    documents = URL(r"/selfcare/documents$", DocumentsPage)
    login = URL(
        r"https://am-gateway\.april\.fr/selfcare/login\?client_id=(?P<client_id>.*)&response_type=code&redirect_uri=https://monespace.april.fr/$",
        LoginPage,
    )
    home = URL(r"https://monespace\.april\.fr/\?code=(?P<login>.*)", HomePage)

    token = None

    def build_request(self, req, *args, **kwargs):
        headers = kwargs.setdefault("headers", {})

        if isinstance(req, requests.Request):
            url = req.url
        else:
            url = req
        if "api-gateway" in url:
            headers["Accept"] = "application/json"
            headers["Content-Type"] = "application/json;charset=UTF-8"
            headers["X-selfcare-filiale"] = "ASP"
            headers["X-selfcare-marque"] = "APRIL"

        return super().build_request(req, *args, **kwargs)

    def do_login(self):
        self.access_token = None
        if self.auth_uri:
            self.request_access_token(self.auth_uri)
        else:
            self.request_authorization()

    def request_authorization(self):
        try:
            self.login.go(client_id=self.client_id)
            self.page.login(self.username, self.password)
            if self.home.is_here():
                self.code = parse_qs(urlparse(self.url).query).get("code")[0]
                payload = {
                    "grant_type": "authorization_code",
                    "code": self.code,
                    "redirect_uri": "https://monespace.april.fr/",
                    "client_id": self.client_id,
                }
                self.update_token(self.do_token_request(payload).json())
        except ClientError as e:
            if e.response.status_code == 400:
                json = e.response.json()
                message = json["error_description"]
                raise BrowserIncorrectPassword(message)
            if e.response.status_code == 429:
                raise BrowserTooManyRequests()
            raise e

    @need_login
    def get_profile(self):
        self.profile.stay_or_go()
        profile = self.page.get_profile()
        return profile

    def iter_subscription(self):
        s = Subscription()
        s.label = "Documents"
        s.id = "documents"
        s._type = s.id
        yield s

    @need_login
    def iter_documents(self):
        self.documents.go()
        docs = self.page.iter_documents()

        # documents are not sorted, sort them directly by reverse date
        docs = sorted(
            docs,
            key=lambda doc: doc.date if doc.date != NotAvailable else date(1900, 1, 1),
            reverse=True,
        )
        for doc in docs:
            yield doc
