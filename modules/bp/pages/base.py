# -*- coding: utf-8 -*-

# Copyright(C) 2010-2016  budget-insight
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

from woob.browser.filters.standard import CleanText
from woob.browser.pages import HTMLPage
from woob.exceptions import BrowserUnavailable


class MyHTMLPage(HTMLPage):
    def on_load(self):
        unavail_msg = CleanText(
            '//main/h1[contains(text(), "Le service est momentanément indisponible.")]'
        )(self.doc)
        if unavail_msg:
            raise BrowserUnavailable(unavail_msg)

        deconnexion = self.doc.xpath('//iframe[contains(@id, "deconnexion")] | //p[@class="txt" and contains(text(), "Session expir")]')
        if deconnexion:
            self.browser.do_login()
