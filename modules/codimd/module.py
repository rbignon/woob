# -*- coding: utf-8 -*-

# Copyright(C) 2012-2020  Budget Insight
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


from woob.tools.backend import Module, BackendConfig
from woob.tools.value import Value, ValueBackendPassword
from woob.capabilities.content import CapContent

from .browser import CodimdBrowser


__all__ = ['CodimdModule']


class CodimdModule(Module, CapContent):
    NAME = 'codimd'
    DESCRIPTION = 'HedgeDoc'
    MAINTAINER = 'Vincent A'
    EMAIL = 'dev@indigo.re'
    LICENSE = 'LGPLv3+'
    VERSION = '3.2'

    BROWSER = CodimdBrowser

    CONFIG = BackendConfig(
        Value('baseurl', label='URL of the HedgeDoc instance', default='https://demo.hedgedoc.org/'),
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
