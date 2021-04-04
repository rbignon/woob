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

from weboob.browser.switch import SwitchingBrowser

from .browser import EdfproBrowser
from .browser_collectivites import EdfproCollectivitesBrowser


class ProxyBrowser(SwitchingBrowser):
    BROWSERS = {
        'main': EdfproBrowser,
        'collectivites': EdfproCollectivitesBrowser,
    }

    KEEP_SESSION = True

    def set_browser(self, name):
        old_browser = self._browser
        super(ProxyBrowser, self).set_browser(name)
        if old_browser:
            self._browser.response = old_browser.response
            self._browser.url = old_browser.url
