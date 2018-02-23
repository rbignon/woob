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


import json
from weboob.browser import LoginBrowser, URL, need_login
from weboob.exceptions import BrowserIncorrectPassword
from weboob.browser.exceptions import ClientError

from .pages import LoginPage, ProfilPage, DocumentsPage, HomePage


class DeliverooBrowser(LoginBrowser):
    BASEURL = 'https://deliveroo.fr'

    home = URL('/fr/$', HomePage)
    login = URL('/fr/login', LoginPage)
    profil = URL('/fr/account$', ProfilPage)
    documents = URL('/fr/orders', DocumentsPage)

    def __init__(self, *args, **kwargs):
        super(DeliverooBrowser, self).__init__(*args, **kwargs)
        self.cache = {}
        self.cache['docs'] = {}

    def do_login(self):
        self.login.go()
        self.session.headers.update({'x-csrf-token': self.page.get_csrf_token()})
        try:
            self.location('/fr/auth/login',
                          data=json.dumps({'email': self.username, 'password': self.password}),
                          headers={'content-type': 'application/json;charset=UTF-8'})
        except ClientError:
            raise BrowserIncorrectPassword()

    @need_login
    def get_subscription_list(self):
        if 'subs' not in self.cache.keys():
            self.profil.stay_or_go()
            assert self.profil.is_here()

            self.cache['subs'] = [self.page.get_item()]
        return self.cache['subs']

    @need_login
    def iter_documents(self, subscription):
        if subscription.id not in self.cache['docs']:
            self.documents.stay_or_go()
            assert self.documents.is_here()

            docs = [d for d in self.page.get_documents(subid=subscription.id)]
            self.cache['docs'][subscription.id] = docs
        return self.cache['docs'][subscription.id]
