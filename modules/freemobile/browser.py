# -*- coding: utf-8 -*-

# flake8: compatible

# Copyright(C) 2012-2014 Florent Fourcot
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

import itertools

from weboob.browser import LoginBrowser, URL, need_login
from weboob.exceptions import BrowserIncorrectPassword

from .pages import LoginPage, BillsPage, ProfilePage, PdfPage, OfferPage

__all__ = ['Freemobile']


class Freemobile(LoginBrowser):
    BASEURL = 'https://mobile.free.fr'

    login_page = URL(r'/account/$', LoginPage)
    logoutpage = URL(r'/account/\?logout=user', LoginPage)
    pdfpage = URL(r'/account/conso-et-factures\?facture=pdf', PdfPage)
    bills = URL(r'/account/conso-et-factures', BillsPage)
    profile = URL(r'/account/mes-informations', ProfilePage)
    offerpage = URL(r'/account/mon-offre', OfferPage)

    def do_login(self):
        self.login_page.go()
        if not self.page.logged:
            self.page.login(self.username, self.password)

        if not self.page.logged:
            error = self.page.get_error()
            if "nom d'utilisateur ou mot de passe incorrect" in error.lower():
                raise BrowserIncorrectPassword(error)
            elif error:
                raise AssertionError('Unexpected error at login: %s' % error)
            raise AssertionError('Unexpected error at login')

    def do_logout(self):
        self.logoutpage.go()
        self.session.cookies.clear()

    @need_login
    def iter_subscription(self):
        offerpage = self.offerpage.stay_or_go()
        subscriptions = itertools.chain([offerpage.get_first_subscription()], offerpage.iter_next_subscription())

        for subscription in subscriptions:
            self.login_page.go(params={"switch-user": subscription._userid})
            self.offerpage.go()
            self.page.fill_subscription(subscription)
            yield subscription


    @need_login
    def iter_documents(self, subscription):
        self.bills.stay_or_go()
        return self.page.iter_documents(sub=subscription.id)

    @need_login
    def get_profile(self):
        self.profile.go()
        return self.page.get_profile()
