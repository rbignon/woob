# -*- coding: utf-8 -*-

# Copyright(C) 2020      Vincent A
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

# flake8: compatible

from __future__ import unicode_literals

from weboob.browser import LoginBrowser, URL, need_login

from .pages import BillsPage, ProfilePage


class EnercoopBrowser(LoginBrowser):
    BASEURL = 'https://espace-client.enercoop.fr'

    login = URL('/login')
    bills = URL(
        r'/mon-espace/factures/',
        r'/mon-espace/factures/\?c=(?P<id>\d+)',
        BillsPage
    )

    profile = URL(
        r'/mon-espace/compte/',
        r'/mon-espace/compte/\?c=(?P<id>\d+)',
        ProfilePage
    )

    def do_login(self):
        self.login.go(data={
            'email': self.username,
            'password': self.password,
        })

    def export_session(self):
        return {
            **super().export_session(),
            'url': self.bills.build(),
        }

    @need_login
    def iter_subscription(self):
        self.bills.go()
        subs = {sub.id: sub for sub in self.page.iter_other_subscriptions()}
        if subs:
            self.bills.go(id=next(iter(subs)))
            subs.update({sub.id: sub for sub in self.page.iter_other_subscriptions()})

            for sub in subs:
                self.profile.go(id=sub)
                self.page.fill_sub(subs[sub])

            return subs.values()

        raise NotImplementedError("how to get info when no selector?")

    @need_login
    def iter_documents(self, id):
        self.bills.go(id=id)
        return self.page.iter_documents()

    @need_login
    def download_document(self, document):
        return self.open(document.url).content
