# -*- coding: utf-8 -*-

# Copyright(C) 2021      Vincent A
#
# This file is part of a woob module.
#
# This woob module is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This woob module is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this woob module. If not, see <http://www.gnu.org/licenses/>.

# flake8: compatible

from woob.browser import PagesBrowser, URL
from woob.capabilities.base import StringField
from woob.capabilities.date import DateField
from woob.capabilities.paste import BasePaste

from .pages import ReadPage, WritePage, encrypt


class PrivatePaste(BasePaste):
    expire = DateField('Expire date')
    delete_url = StringField('URL for deleting paste')

    @property
    def page_url(self):
        return self.url


class JsonURL(URL):
    def handle(self, response):
        if response.headers.get('content-type') != 'application/json':
            return
        return super(JsonURL, self).handle(response)


class PrivatebinBrowser(PagesBrowser):
    BASEURL = 'https://privatebin.net/'

    read_page = JsonURL(r'/\?(?P<id>[\w+-]+)$', ReadPage)
    write_page = JsonURL('/', WritePage)

    def __init__(self, baseurl, opendiscussion, *args, **kwargs):
        super(PrivatebinBrowser, self).__init__(*args, **kwargs)
        self.BASEURL = baseurl
        self.opendiscussion = opendiscussion

    def _find_page(self, subid):
        self.read_page.go(id=subid, headers={"Accept": "application/json"})
        if self.page.has_paste():
            return self.url

    def get_paste(self, id):
        if id.startswith('http://') or id.startswith('https://'):
            url = id
            server_url, key = url.split('#')
            m = self.read_page.match(server_url)
            if not m:
                return
            subid = m.group('id')
            id = '%s#%s' % (subid, key)

            self.location(server_url, headers={"Accept": "application/json"})
            if not self.read_page.is_here():
                return
            elif not self.page.has_paste():
                return
        else:
            subid, key = id.split('#')
            server_url = self._find_page(subid)
            if not server_url:
                return
            url = '%s#%s' % (server_url, key)

        ret = PrivatePaste(id)
        ret.url = url
        ret.contents = self.page.decode_paste(key)
        ret.public = False
        ret.title = self.page.params['id']
        if hasattr(self.page, 'get_expire'):
            ret.expire = self.page.get_expire()
        return ret

    def can_post(self, contents, max_age):
        if max_age not in WritePage.AGES:
            return 0

        # TODO reject binary files on zerobin?
        return 1

    def post_paste(self, p, max_age):
        to_post, url_key = encrypt(p.contents)

        self.location(self.BASEURL, json=to_post, headers={'Accept': 'application/json'})
        self.page.fill_paste(p)
        p.title = p._serverid
        p.id = f"{p._serverid}#{url_key}"
        p.url = self.read_page.build(id=p.id)

        # p.delete_url = self.page.get_delete_url()
