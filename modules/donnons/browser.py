# Copyright(C) 2020      Vincent A
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

from woob.browser import URL, LoginBrowser, need_login
from woob.tools.capabilities.messages.threading import build_linear_thread

from .pages import AdsThreadsPage, LoginPage, ThreadNextPage, ThreadPage, ThreadsPage


class DonnonsBrowser(LoginBrowser):
    BASEURL = "https://donnons.org/"

    login = URL(r"/connexion", LoginPage)
    ads_threads_list = URL(r"/messagerie/annonces$", AdsThreadsPage)
    threads_list = URL(r"/messagerie/annonces/(?P<ad>\d+)\?order=default&page=1", ThreadsPage)
    thread = URL(r"/messagerie/annonces/(?P<ad>\d+)/(?P<thread>\d+)\?order=default&page=1", ThreadPage)
    thread_next = URL(r"/messagerie/ajaxLoadMessages", ThreadNextPage)

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
    def iter_ad_threads(self, ad):
        self.threads_list.go(ad=ad.id)
        for thread in self.page.iter_threads():
            thread.ad = ad
            thread.title = f"{ad.title} - {thread.sender}"
            yield thread

    @need_login
    def iter_messages(self, thread):
        ad_id, thread_id = thread.id.split(".")
        self.thread.go(ad=ad_id, thread=thread_id)

        thread.root = None

        messages = list(self.page.iter_messages())
        total = self.page.get_total_count()

        for page_no in range(2, 10):
            if len(messages) >= total:
                break

            self.thread_next.go(
                data={
                    "conv_id": thread_id,
                    "page": page_no,
                },
                headers={"X-Requested-With": "XMLHttpRequest"},
            )

            new_messages = list(self.page.iter_messages())
            if not new_messages:
                # safety net
                self.logger.warning("no new message on page %r for thread %r", page_no, thread.id)
                break

            # pages are from newest to oldest
            messages = new_messages + messages
        else:
            self.logger.warning("hit safety net when querying next pages of thread %r", thread.id)

        build_linear_thread(messages, thread)
        return messages

    def iter_threads(self):
        for ad in self.iter_ads_threads():
            yield from self.iter_ad_threads(ad)

    def fill_thread(self, thread):
        # this will build the tree
        list(self.iter_messages(thread))
