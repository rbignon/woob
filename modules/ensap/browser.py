# -*- coding: utf-8 -*-

# Copyright(C) 2017      Juliette Fourcot
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

from woob.browser import URL, LoginBrowser, need_login
from woob.capabilities.base import find_object
from woob.capabilities.bill import DocumentNotFound
from woob.exceptions import BrowserIncorrectPassword

from .pages import HomePage, LoginPage, DocumentsPage, BoardPage


class EnsapBrowser(LoginBrowser):
    BASEURL = 'https://ensap.gouv.fr'

    home = URL(r'/$', HomePage)
    login = URL(r'/authentification', LoginPage)
    board = URL(r'/prive/initialiserhabilitation/v1', BoardPage)
    documents = URL(r'/prive/remunerationpaie/v1\?annee=(?P<year>\d+)', DocumentsPage)

    def __init__(self, *args, **kwargs):
        super(EnsapBrowser, self).__init__(*args, **kwargs)
        self.session.headers['Accept'] = 'application/json, text/plain, */*'

    def do_login(self):
        self.login.go(
            data={
                "identifiant": self.username,
                "secret": self.password,
            }
        )

        msg = self.page.get_error_message()
        if 'errone' in msg:
            raise BrowserIncorrectPassword()

    @need_login
    def iter_subscription(self):
        self.board.go(method='POST', json={})
        return self.page.iter_subscription()


    @need_login
    def iter_documents(self, subscription):
        self.board.go(method='POST', json={})
        for year in self.page.get_years():
            self.documents.stay_or_go(year=year)
            for doc in self.page.iter_documents():
                yield doc


    @need_login
    def get_document(self, id):
        return find_object(
            self.iter_documents(None), id=id, error=DocumentNotFound()
        )
