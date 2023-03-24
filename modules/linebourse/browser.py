# -*- coding: utf-8 -*-

# Copyright(C) 2017      Vincent Ardisson
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

from datetime import date, timedelta

from babel.dates import format_date

from woob.browser import LoginBrowser, URL
from woob.browser.exceptions import ClientError
from woob.tools.capabilities.bank.transactions import sorted_transactions

from .pages import (
    PortfolioPage, NewWebsiteFirstConnectionPage, AccountCodesPage, HistoryAPIPage, MarketOrderPage,
)


class LinebourseNoSpace(AssertionError):
    """
    Raise when the account has no linebourse space.
    """
    pass


class LinebourseAPIBrowser(LoginBrowser):
    BASEURL = 'https://www.offrebourse.com'

    # This is temporary because direct import woob_modules feature is not yet possible with woob oss
    # TODO: when possible, remove this, and import directly in the other modules
    # (from woob_modules.linebourse.browser import LinebourseNoSpace)
    LinebourseNoSpace = LinebourseNoSpace

    new_website_first = URL(r'/rest/premiereConnexion', NewWebsiteFirstConnectionPage)
    account_codes = URL(r'/rest/compte/liste/vide/0', AccountCodesPage)

    # The API works with an encrypted account_code that starts with 'CRY'
    portfolio = URL(r'/rest/portefeuille/(?P<account_code>CRY[\w\d]+)/vide/true/false', PortfolioPage)
    history = URL(
        r'/rest/historiqueOperations/legacy/(?P<account_code>CRY[\w\d]+)/(?P<start_date>[^/]+)/(?P<end_date>[^/]+)/7/1',
        HistoryAPIPage
    )
    market_order = URL(
        r'/rest/carnetOrdre/(?P<account_code>CRY[\w\d]+)/segmentation/(?P<index>\d+)/2/1',
        MarketOrderPage
    )

    def __init__(self, baseurl, *args, **kwargs):
        self.BASEURL = baseurl
        super(LinebourseAPIBrowser, self).__init__(username='', password='', *args, **kwargs)

    def get_account_code(self, account_id):
        # 'account_codes' is a JSON containing the id_contracts
        # of all the accounts present on the Linebourse space.
        self.account_codes.go()
        # Some connections have no linebourse space available
        if self.page.is_linebourse_space_available():
            return self.page.get_contract_number(account_id)
        self.logger.warning('Linebourse space is not available for this account.')

    def go_account_codes(self, params):
        """
        Can be called by other modules to access linebourse space.
        """
        try:
            self.account_codes.go(params=params)
        except ClientError as e:
            if e.response.status_code == 400:
                # if bred user have no linebourse space it returns a 400
                raise LinebourseNoSpace()
            raise AssertionError(
                'Unhandled error while fetching linebourse accounts (status code: %d)' % e.response.status_code
            )
        else:
            # This may happen when requesting accounts twice. The status will be 200 but the content contains the error.
            if not self.page.is_linebourse_space_available():
                raise LinebourseNoSpace()

    def go_portfolio(self, account_id):
        account_code = self.get_account_code(account_id)
        return self.portfolio.go(account_code=account_code)

    def iter_investments(self, account_id):
        account_code = self.get_account_code(account_id)
        # We cannot fetch investments if linebourse space is not available
        if not account_code:
            return []
        self.portfolio.go(account_code=account_code)
        date = self.page.get_date()
        account_currency = self.page.get_account_currency()
        return self.page.iter_investments(date=date, account_currency=account_currency)

    def iter_history(self, account_id):
        account_code = self.get_account_code(account_id)
        # We cannot fetch history if linebourse space is not available
        if not account_code:
            return []
        # History available is up to 12 months.
        # Dates in the URL are formatted like `Tue Dec 01 2020 11:43:32 GMT+0100 (heure normale d’Europe centrale)`
        # We can shorten it to `Dec 01 2020`
        end_date = date.today()
        start_date = end_date - timedelta(days=365)
        self.history.go(
            account_code=account_code,
            start_date=format_date(start_date, 'MMM dd yyyy', locale='en'),
            end_date=format_date(end_date, 'MMM dd yyyy', locale='en'),
        )
        # Transactions are not correctly ordered in each JSON
        return sorted_transactions(self.page.iter_history())

    def iter_market_orders(self, account_id):
        account_code = self.get_account_code(account_id)
        # We cannot fetch market_orders if linebourse space is not available
        if not account_code:
            return []
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
