# Copyright(C) 2023      Hugues Mitonneau
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


from woob.browser import URL, LoginBrowser, need_login
from woob.capabilities.bill import Document, Subscription
from woob.exceptions import BrowserIncorrectPassword

from .pages import BillingDetailPage, HomePage, LoginErrorPage, LoginPage, MyAccountPage, SubscriptionPage


class EspacecitoyensBrowser(LoginBrowser):
    BASEURL = 'https://www.espace-citoyens.net'

    login = URL('/(?P<city>\w+)/espace-citoyens/Home/AccueilPublic$', LoginPage)
    home  = URL('/(?P<city>\w+)/espace-citoyens/CompteCitoyen', HomePage)
    loginerror = URL('/(?P<city>\w+)/espace-citoyens/Home/Logon', LoginErrorPage)
    my_account = URL('/(?P<city>\w+)/espace-citoyens/MonCompte$', MyAccountPage)
    subscription = URL('/(?P<city>\w+)/espace-citoyens/FichePersonne/DetailPersonne[?]idDynamic=(?P<sub_id>.*)', SubscriptionPage)
    billing_detail = URL('/(?P<city>\w+)/espace-citoyens/MonCompte/DetailFacture[?]IdFactureUnique=(?P<doc_id>.*)', BillingDetailPage)

    def __init__(self, username, password, city, *args, **kwargs):
        super().__init__(username, password, *args, **kwargs)
        self.city = city

    def do_login(self):
        self.login.stay_or_go(city=self.city)
        self.page.login(self.username, self.password)
        if self.loginerror.is_here():
            raise BrowserIncorrectPassword(self.page.get_error())

    @need_login
    def get_subscription(self, _id):
        self.subscription.stay_or_go(city=self.city, sub_id=_id)
        return self.page.get_subscription()

    @need_login
    def iter_subscriptions(self):
        self.home.stay_or_go(city=self.city)
        return self.page.get_subscriptions()

    @need_login
    def iter_documents(self, subscription):
        if isinstance(subscription, Subscription):
            sub_id = subscription.id
        else:
            sub_id = subscription
        if sub_id != '1':
            return []
        self.my_account.stay_or_go(city=self.city)
        return self.page.iter_documents()

    @need_login
    def get_document(self, document):
        if isinstance(document, Document):
            doc_id = document.id
        else:
            doc_id = document
        self.my_account.stay_or_go(city=self.city)
        self.billing_detail.go(city=self.city, doc_id=doc_id, headers={
            'X-Requested-With': 'XMLHttpRequest',
        })
        return self.page.get_document()

    @need_login
    def download_document(self, document):
        if not isinstance(document, Document):
            document = self.get_document(document)
        self.my_account.stay_or_go(city=self.city)
        return self.open(document.url).content
