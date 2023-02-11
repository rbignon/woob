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

from woob.browser import URL, LoginBrowser, need_login
from woob.exceptions import BrowserIncorrectPassword
from woob.tools.capabilities.bill.documents import sorted_documents

from .pages import LandingPage, SubscriptionPage, DocumentsPage


class MyURL(URL):
    def go(self, *args, **kwargs):
        if not kwargs.get('json'):
            kwargs['json'] = {}
        # because this URL is always supposed to be called like a POST,
        # with a application/json Content-Type, or else it crash
        return super(MyURL, self).go(*args, **kwargs)


class EnsapBrowser(LoginBrowser):
    BASEURL = 'https://ensap.gouv.fr'

    landing = URL(r'/$', LandingPage)
    subscription = MyURL(r'/prive/initialiserhabilitation/v1', SubscriptionPage)
    documents = URL(r'/prive/remunerationpaie/v1\?annee=(?P<year>\d+)', DocumentsPage)
    document_download = URL(r'/prive/telechargerremunerationpaie/v1\?documentUuid=(?P<doc_uuid>.*)')

    def do_login(self):
        data = {
            'identifiant': self.username,
            'secret': self.password
        }
        # this header is mandatory, to avoid receiving an ugly html page,
        # which doesn't tells us if we are logged in or not
        headers = {'accept': 'application/json'}
        self.location('/authentification', data=data, headers=headers)
        if not self.page.logged:
            message = self.page.get_message()
            # message could be "Indentifiant ou mot de passe érroné", yes Indentifiant
            # write dentifiant in case they fix their misspelling
            if 'dentifiant ou mot de passe' in message:
                raise BrowserIncorrectPassword(message)
            raise AssertionError('Unhandled error at login: %s' % message)

    @need_login
    def iter_subscription(self):
        self.subscription.go()
        yield self.page.get_subscription(username=self.username)

    @need_login
    def iter_documents(self):
        self.subscription.stay_or_go()
        for year in self.page.get_years():
            self.documents.stay_or_go(year=year)
            yield from sorted_documents(self.page.iter_documents())
