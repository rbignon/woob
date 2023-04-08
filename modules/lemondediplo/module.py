# -*- coding: utf-8 -*-

# Copyright(C) 2021      Bezleputh
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

from dateutil.rrule import rrule, MONTHLY
from datetime import datetime, timedelta

from woob.tools.backend import Module, BackendConfig
from woob.capabilities.messages import CapMessages, Thread
from woob.capabilities.collection import CapCollection, CollectionNotFound, Collection
from woob.tools.value import ValueBackendPassword
from .browser import LemondediploBrowser


__all__ = ['LemondediploModule']


class LemondediploModule(Module, CapMessages, CapCollection):
    NAME = 'lemondediplo'
    DESCRIPTION = 'lemondediplo website'
    MAINTAINER = 'Bezleputh'
    EMAIL = 'carton_ben@yahoo.fr'
    LICENSE = 'LGPLv3+'
    VERSION = '3.5'
    STORAGE = {'seen': {}}
    BROWSER = LemondediploBrowser
    CONFIG = BackendConfig(ValueBackendPassword('login', label='Identifiant', masked=False),
                           ValueBackendPassword('password', label='Mot de passe'))

    def iter_unread_messages(self):
        pass

    def create_default_browser(self):
        return self.create_browser(self.config['login'].get(), self.config['password'].get())

    def get_thread(self, _id):
        if _id.startswith(self.BROWSER.BASEURL):
            return self.browser.get_thread(_id)
        elif _id.startswith(self.BROWSER.BLOGURL):
            return self.browser.get_blog_thread(_id)
        elif len(_id.split('/')) == 4:
            return self.browser.get_thread(_id)
        else:
            return self.browser.get_blog_thread(_id)

    def iter_threads(self):
        seen = self.storage.get('seen', default={})
        for thread in self.browser.iter_threads():
            if thread.id not in seen.keys():
                yield thread

    def fill_thread(self, thread, fields):
        return self.get_thread(thread.id)

    def set_message_read(self, message):
        self.storage.set('seen', message.thread.id, message.thread.date)
        self.storage.save()
        self._purge_message_read()

    def _purge_message_read(self):
        lastpurge = self.storage.get('lastpurge', default=datetime.now() - timedelta(days=60))

        if datetime.now() - lastpurge > timedelta(days=60):
            self.storage.set('lastpurge', datetime.now() - timedelta(days=60))
            self.storage.save()

            # we can't directly delete without a "RuntimeError: dictionary changed size during iteration"
            todelete = []

            for _id, date in self.storage.get('seen', default={}).items():
                # if no date available, create a new one (compatibility with "old" storage)
                if not date:
                    self.storage.set('seen', _id, datetime.now())
                elif lastpurge > date:
                    todelete.append(_id)

            for _id in todelete:
                self.storage.delete('seen', _id)
            self.storage.save()

    def iter_resources(self, objs, split_path):

        collection = self.get_collection(objs, split_path)

        if collection.path_level == 0:
            coll = [Collection([dt.strftime('%Y-%m')], dt.strftime('%Y-%m')) for dt in
                    rrule(MONTHLY, dtstart=datetime(1954, 1, 1), until=datetime.today())]
            coll.reverse()
            coll.insert(0, Collection(['blogs'], 'Blogs'))

            return coll

        if collection.path_level == 1:
            if collection.basename == "blogs":
                threads = self.browser.iter_blog_threads()
            else:
                threads = self.browser.handle_archives(collection.split_path[0])

            seen = self.storage.get('seen', default={})
            for thread in threads:
                if thread.id not in seen.keys():
                    yield thread

    def validate_collection(self, objs, collection):

        if collection.path_level == 0:
            return
        elif collection.path_level == 1 and\
            (collection.split_path[0] == 'blogs' or collection.split_path[0] in
             [dt.strftime('%Y-%m') for dt in rrule(MONTHLY, dtstart=datetime(1954, 1, 1), until=datetime.today())]):
            return
        elif Thread in objs:
            return

        raise CollectionNotFound(collection.split_path)

    OBJECTS = {Thread: fill_thread}
