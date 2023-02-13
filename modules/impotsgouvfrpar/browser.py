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

# flake8: compatible

from woob.browser import URL, need_login
from woob.exceptions import BrowserIncorrectPassword
from woob.tools.capabilities.bill.documents import sorted_documents
from woob_modules.franceconnect.browser import FranceConnectBrowser
from woob_modules.franceconnect.pages import ImpotsLoginAccessPage, ImpotsLoginAELPage, ImpotsGetContextPage

from .pages import (
    ProfilePage, DocumentsPage, ThirdPartyDocPage, NoDocumentPage,
    ErrorDocumentPage, HomePage, FCAuthorizePage,
)


class ImpotsParBrowser(FranceConnectBrowser):
    BASEURL = 'https://cfspart.impots.gouv.fr'
    PARENT = 'franceconnect'

    authorize = URL(r'https://app.franceconnect.gouv.fr/api/v1/authorize', FCAuthorizePage)
    impot_login_page = URL(r'/LoginAccess', ImpotsLoginAccessPage)
    impot_login_ael = URL(r'/LoginAEL', ImpotsLoginAELPage)
    impot_get_context = URL(r'/GetContexte', ImpotsGetContextPage)
    home = URL(
        r"/monprofil-webapp/connexion",
        r"/enp/ensu/accueilensupres.do",
        r"/enp/accueil.ex",
        r"/enp/j_appelportail",
        r"/enp/j_accueil;jsessionid=(?P<jsessionid>.*)",
        r"/enp/\?urlDest=(?P<url>.*)",
        HomePage
    )
    third_party_doc_page = URL(r'/enp/ensu/dpr.do', ThirdPartyDocPage)
    no_document_page = URL(r'/enp/ensu/documentabsent.do', NoDocumentPage)
    error_document_page = URL(r'/enp/ensu/drpabsent.do', ErrorDocumentPage)

    profile = URL(
        r'/enp/ensu/chargementprofil.do',
        r'/enp/?$',
        ProfilePage
    )
    documents = URL(r'/enp/ensu/documents.do', DocumentsPage)

    def __init__(self, login_source, *args, **kwargs):
        super(ImpotsParBrowser, self).__init__(*args, **kwargs)
        self.login_source = login_source

    def france_connect_do_login(self):
        self.location('https://cfsfc.impots.gouv.fr/', data={'lmAuth': 'FranceConnect'})
        self.login_impots()
        # Needed to set cookies to be able to access profile page
        # without being disconnected
        self.home.go()

    def france_connect_ameli_do_login(self):
        self.location('https://cfsfc.impots.gouv.fr/', data={'lmAuth': 'FranceConnect'})
        if self.page.is_ameli_disabled():
            # Message on the website "Non disponible sur ce service"
            raise BrowserIncorrectPassword(
                "La connection via Ameli n'est plus disponible.",
                bad_fields=['login', 'password', 'login_source']
            )
        self.login_ameli()
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
        self.impot_login_page.go()
        self.login_impots(fc_redirection=False)
        if not self.page.logged:
            raise BrowserIncorrectPassword(bad_fields=['password'])

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
