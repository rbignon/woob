# -*- coding: utf-8 -*-

# Copyright(C) 2012-2020  Budget Insight
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

from woob.browser import AbstractBrowser, URL, need_login
from woob.exceptions import BrowserIncorrectPassword
from woob.tools.capabilities.bill.documents import sorted_documents

from .pages import (
    LoginAccessPage, LoginAELPage, ProfilePage, DocumentsPage,
    ThirdPartyDocPage, NoDocumentPage, ErrorDocumentPage,
    GetContextePage, HomePage
)


class ImpotsParBrowser(AbstractBrowser):
    BASEURL = 'https://cfspart.impots.gouv.fr'
    PARENT = 'franceconnect'

    login_access = URL(r'/LoginAccess', LoginAccessPage)
    login_ael = URL(r'/LoginAEL', LoginAELPage)
    get_contexte = URL(r"/GetContexte", GetContextePage)
    home          = URL(r"/monprofil-webapp/connexion",
                        r"/enp/ensu/accueilensupres.do",
                        r"/enp/accueil.ex",
                        r"/enp/j_appelportail",
                        r"/enp/j_accueil;jsessionid=(?P<jsessionid>.*)",
                        r"/enp/\?urlDest=(?P<url>.*)", HomePage)
    third_party_doc_page = URL(r'/enp/ensu/dpr.do', ThirdPartyDocPage)
    no_document_page = URL(r'/enp/ensu/documentabsent.do', NoDocumentPage)
    error_document_page = URL(r'/enp/ensu/drpabsent.do', ErrorDocumentPage)

    # affichageadresse.do is pretty similar to chargementprofil.do but display address
    profile = URL(
        r'/enp/ensu/affichageadresse.do',
        r'/enp/?$',
        ProfilePage
    )
    documents = URL(r'/enp/ensu/documents.do', DocumentsPage)

    def __init__(self, login_source, *args, **kwargs):
        super(ImpotsParBrowser, self).__init__(*args, **kwargs)
        self.login_source = login_source

    def login_impots(self):
        # 1bis) start with LoginAccessPage
        contexte_url = self.page.url_contexte
        url_login_mot_de_passe = self.page.url_login_mot_de_passe

        # Note : I'd prefer to use `response = self.open(...)` below
        # but it does not seem to execute page.on_load() ??
        # Instead, saving current page to use it later
        login_page = self.page

        # 2) POST /GetContexte (GetContextePage)
        self.location(contexte_url, data={"spi": self.username})

        if not self.page.handle_message():
            raise BrowserIncorrectPassword('wrong login')

        # 3) POST /LoginAEL (LoginAELPage)
        login_page.login(
            self.username, self.password,
            url_login_mot_de_passe,
        )

        # 4) GET /enp/ (HomePage) (case direct)
        # or GET ...authorize (case fc)
        next_page = self.page.handle_message()
        self.location(next_page)

    def login_ameli(self):
        self.page.login(self.username, self.password)

        if self.ameli_wrong_login_page.is_here():
            raise BrowserIncorrectPassword(self.page.get_error_message())

    def france_connect_do_login(self):
        self.location('https://cfsfc.impots.gouv.fr/', data={'lmAuth': 'FranceConnect'})
        self.fc_call('dgfip', 'https://idp.impots.gouv.fr')
        self.login_impots()
        self.fc_redirect()
        # Needed to set cookies to be able to access profile page
        # without being disconnected
        self.home.go()

    def france_connect_ameli_do_login(self):
        self.location('https://cfsfc.impots.gouv.fr/', data={'lmAuth': 'FranceConnect'})
        self.fc_call('ameli', 'https://fc.assure.ameli.fr')
        self.login_ameli()
        self.fc_redirect()
        # Needed to set cookies to be able to access profile page
        # without being disconnected
        self.location('https://cfsfc.impots.gouv.fr/enp/')

    def do_login(self):
        if self.login_source == 'fc':
            self.france_connect_do_login()
            return

        if self.login_source == 'fc_ameli':
            self.france_connect_ameli_do_login()
            return

        # 1) GET /LoginAccess (LoginAccessPage)
        self.login_access.go()
        self.login_impots()
        if not self.page.logged:
            raise BrowserIncorrectPassword('wrong password')

    @need_login
    def iter_subscription(self):
        return self.profile.go().get_subscriptions()

    @need_login
    def iter_documents(self, subscription):
        # it's a document json which is used in the event of a declaration by a third party
        self.third_party_doc_page.go()

        third_party_doc = None
        if self.error_document_page.is_here():
            self.logger.warning('Third party declaration is unavailable')
        elif self.third_party_doc_page.is_here():
            third_party_doc = self.page.get_third_party_doc()

        # put ?n=0, else website return an error page
        self.documents.go(params={'n': 0})
        doc_list = sorted_documents(self.page.iter_documents(subid=subscription.id))
        if third_party_doc:
            doc_list.insert(0, third_party_doc)

        return doc_list

    @need_login
    def get_profile(self):
        self.profile.go()
        return self.page.get_profile()
