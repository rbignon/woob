# -*- coding: utf-8 -*-

# Copyright(C) 2017      Vincent Ardisson
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

from weboob.browser import LoginBrowser, URL
from weboob.browser.exceptions import ClientError
from weboob.tools.capabilities.bank.transactions import sorted_transactions

from .pages import (
    PortfolioPage, NewWebsiteFirstConnectionPage, AccountCodesPage,
    HistoryAPIPage, MarketOrderPage,
)


class LinebourseAPIBrowser(LoginBrowser):
    BASEURL = 'https://www.offrebourse.com'

    new_website_first = URL(r'/rest/premiereConnexion', NewWebsiteFirstConnectionPage)
    account_codes = URL(r'/rest/compte/liste/vide/0', AccountCodesPage)

    # The API works with an encrypted account_code that starts with 'CRY'
    portfolio = URL(r'/rest/portefeuille/(?P<account_code>CRY[\w\d]+)/vide/true/false', PortfolioPage)
    history = URL(r'/rest/historiqueOperations/(?P<account_code>CRY[\w\d]+)/(?P<month_idx>\d+)/7/1', HistoryAPIPage)
    market_order = URL(r'/rest/carnetOrdre/(?P<account_code>CRY[\w\d]+)/segmentation/(?P<index>\d+)/2/1', MarketOrderPage)

    def __init__(self, baseurl, *args, **kwargs):
        self.BASEURL = baseurl
        super(LinebourseAPIBrowser, self).__init__(username='', password='', *args, **kwargs)

    def get_account_code(self, account_id):
        # 'account_codes' is a JSON containing the id_contracts
        # of all the accounts present on the Linebourse space.
        self.account_codes.go()
        return self.page.get_contract_number(account_id)

    def go_portfolio(self, account_id):
        account_code = self.get_account_code(account_id)
        return self.portfolio.go(account_code=account_code)

    def iter_investments(self, account_id):
        self.go_portfolio(account_id)
        date = self.page.get_date()
        return self.page.iter_investments(date=date)

    def iter_history(self, account_id):
        account_code = self.get_account_code(account_id)
        # History available is up to 3 months.
        # For each month we have to pass the month index.
        for month_idx in range(3):
            self.history.go(
                account_code=account_code,
                month_idx=month_idx,
            )
            # Transactions are not correctly ordered in each JSON
            for tr in sorted_transactions(self.page.iter_history()):
                yield tr

    def iter_market_orders(self, account_id):
        account_code = self.get_account_code(account_id)
        market_orders = []

        # Each index from 0 to 4 corresponds to various order books types.
        # For some connections, the request with index 4 (foreign orders)
        # returns a 400 error so we must handle it accordingly.
        for index in range(4):
            self.market_order.go(
                account_code=account_code,
                index=index,
            )
            market_orders.extend(self.page.iter_market_orders())

        # Try to fetch market orders on 'Carnet d'ordres Bourse étrangère'
        try:
            self.market_order.go(
                account_code=account_code,
                index=4,
            )
        except ClientError:
            self.logger.warning('Foreign orders book is not accessible for this account.')
        else:
            market_orders.extend(self.page.iter_market_orders())

        return sorted(market_orders, reverse=True, key=lambda order: order.date)
