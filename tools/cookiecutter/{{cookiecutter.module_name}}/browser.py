# -*- coding: utf-8 -*-

# Copyright(C) {{cookiecutter.year}} {{cookiecutter.full_name}}
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

from __future__ import unicode_literals

from woob.browser import LoginBrowser, URL, need_login
from woob.exceptions import BrowserIncorrectPassword

from .pages import (
    LoginPage, SomethingPage,
)


class {{cookiecutter.class_prefix}}Browser(LoginBrowser):
    BASEURL = "{{cookiecutter.site_url}}"

    login = URL(r"/login", LoginPage)
    something = URL(r"/something", SomethingPage)

    def do_login(self):
        self.login.go()
        self.page.do_login(self.username, self.password)

        if self.page.something():
            raise BrowserIncorrectPassword()

    @need_login
    def iter_something(self):
        self.something.go()
        return self.page.iter_something()
