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

from .pages import DocumentsPage, HomePage, LoginPage, LoginValidityPage, UserDataPage


class EnsapBrowser(LoginBrowser):
    BASEURL = 'https://ensap.gouv.fr'

    loginp = URL(r'/web/views/contenus/accueilnonconnecte.html', LoginPage)
    loginvalidity = URL(r'/authentification', LoginValidityPage)
    user_data = URL(r'/prive/initialiserhabilitation/v1', UserDataPage)
    homep = URL(r'/prive/accueilconnecte/v1', HomePage)
    documents = URL(r'/prive/remunerationpaie/v1\?annee=(?P<year>\d+)', DocumentsPage)

    def do_login(self):
        self.logger.debug('call Browser.do_login')

        self.loginp.stay_or_go()
        self.loginvalidity.go(
            data={"identifiant": self.username, "secret": self.password}
        )
        if not self.page.check_logged():
            raise BrowserIncorrectPassword()

    @need_login
    def iter_documents(self, subscription):
        self.user_data.go(method="post", headers={'Content-Type': 'application/json'})
        for year in self.page.get_years():
            self.documents.stay_or_go(year=year)
            for doc in self.page.iter_documents():
                yield doc

    @need_login
    def iter_subscription(self):
        self.homep.stay_or_go()
        return self.page.iter_subscription()

    @need_login
    def get_document(self, id):
        return find_object(
            self.iter_documents(None), id=id, error=DocumentNotFound()
        )
