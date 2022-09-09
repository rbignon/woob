# -*- coding: utf-8 -*-

# flake8: compatible

# Copyright(C) 2012-2014 Florent Fourcot
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

import itertools

from woob.browser import LoginBrowser, URL, need_login
from woob.capabilities.messages import CantSendMessage
from woob.exceptions import BrowserIncorrectPassword, BrowserUnavailable, ActionNeeded

from .pages import LoginPage, BillsPage, ProfilePage, PdfPage, OfferPage, OptionsPage

__all__ = ['Freemobile']


class Freemobile(LoginBrowser):
    BASEURL = 'https://mobile.free.fr'

    login_page = URL(r'/account/$', LoginPage)
    logoutpage = URL(r'/account/\?logout=user', LoginPage)
    pdfpage = URL(r'/account/conso-et-factures\?facture=pdf', PdfPage)
    bills = URL(r'/account/conso-et-factures', BillsPage)
    profile = URL(r'/account/mes-informations', ProfilePage)
    offerpage = URL(r'/account/mon-offre', OfferPage)
    optionspage = URL(r'/account/mes-options', OptionsPage)
    sendAPI = URL(r'https://smsapi.free-mobile.fr/sendmsg\?user=(?P<username>)&pass=(?P<apikey>)&msg=(?P<msg>)')

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
        self.offerpage.stay_or_go()
        if self.login_page.is_here():
            error = self.page.get_error()
            if 'restreint suite à un impayé' in error:
                raise ActionNeeded(error)
            elif 'Vous ne pouvez pas avoir accès à cette page' in error:
                raise BrowserUnavailable(error)
            elif error:
                raise AssertionError('Unexpected error at subscription: %s' % error)

        subscriptions = itertools.chain([self.page.get_first_subscription()], self.page.iter_next_subscription())

        for subscription in subscriptions:
            self.login_page.go(params={"switch-user": subscription.id})
            self.offerpage.go()
            self.page.fill_subscription(subscription)
            yield subscription

    @need_login
    def iter_documents(self, subscription):
        self.login_page.go(params={"switch-user": subscription.id})
        self.bills.stay_or_go()
        return self.page.iter_documents(sub=subscription.id)

    @need_login
    def post_message(self, message):
        receiver = message.thread.id
        username = [
            subscription.id
            for subscription in self.iter_subscription()
            if subscription._phone_number.split("@")[0] == receiver
        ]
        if username:
            username = username[0]
        else:
            raise CantSendMessage(
                'Cannot fetch own number.'
            )

        self.login_page.go(params={"switch-user": username})
        self.optionspage.go()

        api_key = self.page.get_api_key()
        if not api_key:
            raise CantSendMessage(
                'Cannot fetch API key for this account, is option enabled?'
            )

        self.sendAPI.go(
            username=username, apikey=api_key,
            msg=message.content
        )

    @need_login
    def get_profile(self):
        self.profile.go()
        return self.page.get_profile()
