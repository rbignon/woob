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


from weboob.tools.backend import Module, BackendConfig
from weboob.tools.value import Value, ValueBackendPassword
from weboob.capabilities.content import CapContent

from .browser import CodimdBrowser


__all__ = ['CodimdModule']


class CodimdModule(Module, CapContent):
    NAME = 'codimd'
    DESCRIPTION = 'CodiMD'
    MAINTAINER = 'Vincent A'
    EMAIL = 'dev@indigo.re'
    LICENSE = 'LGPLv3+'
    VERSION = '1.6'

    BROWSER = CodimdBrowser

    CONFIG = BackendConfig(
        Value('baseurl', label='URL of the CodiMD instance', default='https://hackmd.io/'),
        ValueBackendPassword('login', label='Email or LDAP username', default=''),
        ValueBackendPassword('password', label='Password', default=''),
    )

    def create_default_browser(self):
        return self.create_browser(
            self.config['baseurl'].get(),
            self.config['login'].get(),
            self.config['password'].get(),
        )

    def get_content(self, id, revision=None):
        return self.browser.get_content(id, revision)

    def iter_revisions(self, id):
        return self.browser.iter_revisions(id)

    def push_content(self, content, message=None, minor=False):
        return self.browser.push_content(content)

    def get_content_preview(self, content):
        # TODO see if it can be done without "publishing the doc"
        # or does publishing not grant more permissions?
        raise NotImplementedError()
