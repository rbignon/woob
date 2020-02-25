# -*- coding: utf-8 -*-

# Copyright(C) 2020      Ludovic LANGE
#
# This file is part of a weboob module.
#
# This weboob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This weboob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this weboob module. If not, see <http://www.gnu.org/licenses/>.

from __future__ import unicode_literals


from weboob.browser import LoginBrowser, need_login, URL
from weboob.capabilities.bill import Subscription
from weboob.capabilities.base import NotAvailable

from .pages import LoginPage, ProfilePage, DocumentsPage
from datetime import date


class AprilBrowser(LoginBrowser):
    BASEURL = "https://monespace.april.fr"

    logout = URL(r"/n/login$")
    login = URL(r"/n/api/security/authenticate$", LoginPage)
    profile = URL(r"/api/personne/informations$", ProfilePage)
    documents = URL(r"/api/documents$", DocumentsPage)

    token = None

    def build_request(self, *args, **kwargs):
        headers = kwargs.setdefault("headers", {})
        headers["Accept"] = "application/json"
        headers["Content-Type"] = "application/json;charset=UTF-8"
        if self.token:
            headers["Authorization"] = "Bearer %s" % self.token

        return super(AprilBrowser, self).build_request(*args, **kwargs)

    def do_login(self):
        login_data = {"user": self.username, "password": self.password}
        self.login.go(json=login_data)
        self.token = self.page.get_token()

    def do_logout(self):
        self.logout.go()
        self.session.cookies.clear()

    @need_login
    def get_profile(self):
        self.profile.go()
        profile = self.page.get_profile()
        return profile

    def iter_subscription(self):
        s = Subscription()
        s.label = "Documents"
        s.id = "documents"
        s._type = s.id
        yield s

    @need_login
    def iter_documents(self, subscription):
        self.documents.go()
        docs = self.page.iter_documents(subscription=subscription.id)

        # documents are not sorted, sort them directly by reverse date
        docs = sorted(
            docs,
            key=lambda doc: doc.date if doc.date != NotAvailable else date(1900, 1, 1),
            reverse=True,
        )
        for doc in docs:
            yield doc
