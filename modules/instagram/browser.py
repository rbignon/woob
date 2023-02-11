# -*- coding: utf-8 -*-

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

import json

from woob.browser import PagesBrowser, URL
from woob.browser.cache import CacheMixin

from .pages import HomePage, OtherPage


class InstagramBrowser(CacheMixin, PagesBrowser):
    BASEURL = 'https://www.instagram.com'

    pagination = URL(r'/graphql/query/', OtherPage)
    home = URL(r'/(?P<user>[^/]+)/', HomePage)

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.is_updatable = True

    open = CacheMixin.open_with_cache

    def iter_images(self):
        self.home.go(user=self.user)
        user_id = self.page.get_user_id()
        author = self.page.get_author_name()

        def set_author(obj):
            obj.author = author
            return obj

        yield from map(set_author, self.page.iter_images())

        while True:
            after = self.page.get_end_cursor()
            if not after:
                return

            self.pagination.go(params={
                'query_hash': 'bfa387b2992c3a52dcbe447467b4b771',
                'variables': json.dumps({
                    'id': user_id,
                    'first': 12,
                    'after': after,
                }),
            })
            yield from map(set_author, self.page.iter_images())
