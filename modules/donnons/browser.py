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

from __future__ import unicode_literals

from woob.browser import LoginBrowser, URL, need_login


from .pages import LoginPage, AdsThreadsPage, ThreadsPage, ThreadPage


class DonnonsBrowser(LoginBrowser):
    BASEURL = 'https://donnons.org/'

    login = URL(r'/connexion', LoginPage)
    ads_threads_list = URL(r'/messagerie/annonces$', AdsThreadsPage)
    threads_list = URL(r'/messagerie/annonces/(?P<ad>\d+)\?order=default&page=1', ThreadsPage)
    thread = URL(r'/messagerie/annonces/(?P<ad>\d+)/(?P<thread>\d+)\?order=default&page=1', ThreadPage)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def do_login(self):
        self.login.go()
        if self.login.is_here():
            self.page.do_login(self.username, self.password)

    @need_login
    def iter_ads_threads(self):
        self.ads_threads_list.go()
        return self.page.iter_ads()

    @need_login
    def iter_threads(self, ad):
        self.threads_list.go(ad=ad.id)
        for thread in self.page.iter_threads():
            thread.ad = ad
            yield thread

    @need_login
    def iter_messages(self, thread):
        self.thread.go(ad=thread.ad.id, thread=thread.id)
        for message in self.page.iter_messages():
            message.thread = thread
            yield message
