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

from weboob.browser import AbstractBrowser, URL, need_login

from .boursedirect_pages import (
    MarketOrdersPage, MarketOrderDetailsPage, AccountsPage, HistoryPage,
)


class BourseDirectBrowser(AbstractBrowser):
    PARENT = 'boursedirect'
    BASEURL = 'https://bourse.ing.fr'

    # These URLs have been updated on Bourse Direct but not on ING.
    # If they are updated on ING, remove these definitions and associated abstract pages.
    accounts = URL(
        r'/priv/compte.php$',
        r'/priv/compte.php\?nc=(?P<nc>\d+)',
        r'/priv/listeContrats.php\?nc=(?P<nc>\d+)',
        AccountsPage
    )
    history = URL(r'/priv/compte.php\?ong=3&nc=(?P<nc>\d+)', HistoryPage)
    market_orders = URL(r'/priv/compte.php\?ong=7', MarketOrdersPage)
    market_orders_details = URL(r'/priv/detailOrdre.php', MarketOrderDetailsPage)

    @need_login
    def iter_market_orders(self, account):
        # 'Bourse Direct' space of ING still uses the old navigation for Market Orders
        if account.type not in (account.TYPE_PEA, account.TYPE_MARKET):
            return

        self.pre_invests.go(nc=account._select)
        self.market_orders.go()
        for order in self.page.iter_market_orders():
            if order.url:
                self.location(order.url)
                if self.market_orders_details.is_here():
                    self.page.fill_market_order(obj=order)
                else:
                    self.logger.warning('Unknown details URL for market order %s.', order.label)
            else:
                self.logger.warning('Market order %s has no details URL.', order.label)
            yield order
