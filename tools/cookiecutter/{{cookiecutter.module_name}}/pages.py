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

from woob.browser.elements import method, ListElement, ItemElement
from woob.browser.filters.html import AbsoluteLink
from woob.browser.filters.standard import (
    CleanText, CleanDecimal, Date,
)
from woob.browser.pages import LoggedPage, HTMLPage


class LoginPage(HTMLPage):
    def login(self, username, password):
        form = self.get_form(id="login")
        form["login"] = username
        form["password"] = password
        form.submit()


class SomethingPage(LoggedPage, HTMLPage):
    @method
    class iter_something(ListElement):
        item_xpath = "//div[@id='something']"

        class item(ItemElement):
            klass = Something

            obj_label = CleanText(".//span[has-class('col-label')]")
            obj_price = CleanDecimal.SI(".//span[has-class('col-amount')]")
            obj_date = Date(CleanText(".//span[has-class('col-date')]"))
            obj_url = AbsoluteLink(".//a")
