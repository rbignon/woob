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

# flake8: compatible

from __future__ import unicode_literals

from weboob.browser.pages import HTMLPage, LoggedPage
from weboob.browser.filters.standard import CleanText, Regexp
from weboob.browser.filters.html import Link


class GenericLandingPage(LoggedPage, HTMLPage):
    """generic page associated with generic operations"""

    def get_middle_frame_url(self):
        return CleanText('//script[contains(@src, "cgi")][1]/@src', default=None)(self.doc)


class JSMiddleFramePage(LoggedPage, HTMLPage):
    """Middle Frame Page"""

    def is_here(self):
        return self.content.decode('iso-8859-1').startswith('var mc')

    def get_patrimoine_url(self):
        return Link('//a[contains(., "Espace Patrimoine")]', default=None)(self.doc)


class JSMiddleAuthPage(LoggedPage, HTMLPage):
    def is_here(self):
        return "https://www.hsbc.fr/1/3/authentication/sso-cwd" in self.content.decode('iso-8859-1')

    def get_middle_auth_link(self):
        return Regexp(CleanText('//body/@onload'), r'top.location.replace\(\'(https://.*)\'\)')(self.doc)

    def go_next(self):
        self.browser.location(self.get_middle_auth_link())


class InvestmentFormPage(LoggedPage, HTMLPage):

    def is_here(self):
        return self.doc.xpath('boolean(//form[@name="launch"])')

    def go_to_logon(self):
        self.get_form(name='launch').submit()
        assert self.browser.logon_investment_page.is_here()
