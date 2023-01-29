# -*- coding: utf-8 -*-

# Copyright(C) 2015      Vincent A
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

import re
from urllib.parse import urljoin

from woob.tools.backend import Module, BackendConfig
from woob.capabilities.paste import CapPaste, BasePaste
from woob.tools.capabilities.paste import image_mime
from woob.tools.value import Value

from .browser import LutimBrowser


__all__ = ['LutimModule']


class LutimModule(Module, CapPaste):
    NAME = 'lutim'
    DESCRIPTION = u"Lutim (Let's Upload That IMage)"
    MAINTAINER = u'Vincent A'
    EMAIL = 'dev@indigo.re'
    LICENSE = 'AGPLv3+'
    VERSION = '3.2'

    BROWSER = LutimBrowser

    CONFIG = BackendConfig(Value('base_url', label='Hoster base URL'))

    @property
    def base_url(self):
        url = self.config['base_url'].get()
        if not url.endswith('/'):
            url = url + '/'
        return url

    def create_default_browser(self):
        return self.create_browser(self.base_url)

    def can_post(self, contents, title=None, public=None, max_age=None):
        if public:
            return 0
        elif max_age and max_age < 86400:
            return 0  # it cannot be shorter than one day
        elif re.search(r'[^a-zA-Z0-9=+/\s]', contents):
            return 0  # not base64, thus not binary
        else:
            mime = image_mime(contents, ('gif', 'jpeg', 'png'))
            return 20 * int(mime is not None)

    def get_paste(self, url):
        if not url.startswith('http'):
            url = urljoin(self.base_url, url)
        paste = self.new_paste(url)
        self.browser.fetch(paste)
        return paste

    def new_paste(self, _id):
        paste = LutimPaste(_id)
        return paste

    def post_paste(self, paste, max_age):
        return self.browser.post(paste, max_age)


class LutimPaste(BasePaste):
    @classmethod
    def id2url(cls, id):
        return id
