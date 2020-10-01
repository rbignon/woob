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

# flake8: compatible

from __future__ import unicode_literals

from weboob.browser.pages import AbstractPage


class AccountsPage(AbstractPage):
    PARENT = 'boursedirect'
    PARENT_URL = 'accounts'
    BROWSER_ATTR = 'package.browser.BoursedirectBrowser'


class HistoryPage(AbstractPage):
    PARENT = 'boursedirect'
    PARENT_URL = 'history'
    BROWSER_ATTR = 'package.browser.BoursedirectBrowser'


class MarketOrdersPage(AbstractPage):
    PARENT = 'boursedirect'
    PARENT_URL = 'market_orders'
    BROWSER_ATTR = 'package.browser.BoursedirectBrowser'


class MarketOrderDetailsPage(AbstractPage):
    PARENT = 'boursedirect'
    PARENT_URL = 'market_orders_details'
    BROWSER_ATTR = 'package.browser.BoursedirectBrowser'
