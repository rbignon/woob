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

from lxml.etree import LxmlError

from woob.browser.filters.standard import CleanText
from woob.browser.pages import HTMLPage
from woob.exceptions import BrowserUnavailable


class IncludedUnavailablePage(HTMLPage):
    """Unavailable page included on another URL.

    It is necessary to define a separate page for this rather than include
    it in MyHTMLPage, since some pages base themselves on the content of
    the page rather than the URL alone, resulting in some unavailable errors
    making the browser page attribute be None instead of a page than could
    raise a BrowserUnavailable.

    Note that this page might be instanciated for other content types,
    such as JSON or images.
    """

    UNAVAILABLE_XPATH = (
        '//main/h1[contains(text(), '
        + '"Le service est momentanément indisponible.")]'
    )

    def build_doc(self, content):
        try:
            return super().build_doc(content)
        except LxmlError:
            return None

    def is_here(self):
        if self.doc is None:
            return False

        return bool(self.doc.xpath(self.UNAVAILABLE_XPATH))

    def on_load(self):
        raise BrowserUnavailable(CleanText(self.UNAVAILABLE_XPATH)(self.doc))


class MyHTMLPage(HTMLPage):
    def on_load(self):
        deconnexion = self.doc.xpath('//iframe[contains(@id, "deconnexion")] | //p[@class="txt" and contains(text(), "Session expir")]')
        if deconnexion:
            self.browser.do_login()
