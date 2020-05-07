# -*- coding: utf-8 -*-

# Copyright(C) 2012-2020  Budget Insight
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

from weboob.browser import PagesBrowser, URL
from weboob.exceptions import BrowserIncorrectPassword, BrowserHTTPNotFound
from weboob.capabilities.content import Content, Revision

from .pages import (
    NotePage, MePage, RootPage, RevisionListPage, RevisionPage, NewNotePage,
)


class CodimdBrowser(PagesBrowser):
    BASEURL = 'https://hackmd.io/'

    login_ldap = URL(r'/auth/ldap')
    login_email = URL(r'/login')
    me = URL(r'/me', MePage)
    note_dl = URL(r'/(?P<note>[a-zA-Z0-9_-]+)/download', NotePage)
    one_revision = URL(r'/(?P<note>[a-zA-Z0-9_-]+)/revision/(?P<rev>\d+)', RevisionPage)
    revisions = URL(r'/(?P<note>[a-zA-Z0-9_-]+)/revision$', RevisionListPage)
    new_note = URL(
        r'/new',
        r'/new/(?P<note>[a-zA-Z0-9_-]+)',
        NewNotePage
    )
    base_note = URL(r'/(?P<note>[a-zA-Z0-9_-]+)$')
    socket = URL(r'/socket.io/\?noteId=(?P<note>[a-zA-Z0-9_-]+)&EIO=3&transport=polling&t=(?P<t>[a-zA-Z]+)')
    root = URL(r'/$', RootPage)

    def __init__(self, baseurl, username, password, *args, **kwargs):
        self.BASEURL = baseurl
        self.username = username
        self.password = password
        super().__init__(*args, **kwargs)

    def do_login(self):
        if not self.username:
            raise BrowserIncorrectPassword('Missing login')
        elif not self.password:
            raise BrowserIncorrectPassword('Missing password')

        if '@' in self.username:
            url = self.login_email
            larg = 'email'
        else:
            url = self.login_ldap
            larg = 'username'

        url.go(data={
            larg: self.username,
            'password': self.password,
        })
        if self.root.is_here():
            self.page.check_error()

        self.me.go()
        assert self.page.doc['status'] == 'ok'

    def _call_with_login(self, func, *args, **kwargs):
        # TODO handle 404 error when note is not found
        func(*args, **kwargs)
        if self.root.is_here() and self.page.requires_auth():
            self.do_login()
            func(*args, **kwargs)

    def get_content(self, id, rev=None):
        if rev:
            return self.get_content_rev(id, rev)
        else:
            return self.get_content_raw(id)

    def get_content_rev(self, id, rev):
        if not isinstance(rev, str):
            rev = rev.id

        self._call_with_login(self.one_revision.go, note=id, rev=rev)

        ret = Content()
        ret.content = self.page.get_content()
        return ret

    def get_content_raw(self, id):
        try:
            self._call_with_login(self.note_dl.go, note=id)
        except BrowserHTTPNotFound:
            return None

        ret = Content()
        ret.url = self.base_note.build(note=id)
        ret.id = id
        ret.title = self.page.get_title()
        ret.content = self.page.text
        return ret

    def iter_revisions(self, id):
        try:
            self._call_with_login(self.revisions.go, note=id)
        except BrowserHTTPNotFound:
            return

        for rev_ts in self.page.get_list():
            rev = Revision()
            rev.id = str(rev_ts)
            rev.timestamp = rev_ts // 1000
            # multiple authors per revision?
            yield rev

    def push_content(self, content):
        if content.id:
            # TODO do we have to do it with /socket.io route?
            raise NotImplementedError('Pushing a new revision is not implemented yet')

        self._call_with_login(
            self.new_note.go, data=content.content,
            headers={'Content-Type': 'text/markdown'},
        )

        match = self.base_note.match(self.url)
        if match:
            content.url = self.url
            content.id = match['note']

            # add the note to user history
            # t= is supposed to be unique? a constant works fine
            self.socket.open(note=content.id, t='WEBOOB')
            return content

    # deleting a note is done in /socket.io route
    # DELETE on /history/<note> only unlinks from history
