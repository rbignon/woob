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

from __future__ import unicode_literals

import datetime
from decimal import Decimal

from woob.browser import LoginBrowser, URL, need_login
from woob.browser.exceptions import ClientError
from woob.exceptions import BrowserIncorrectPassword
from woob.tools.json import json
from woob.tools.capabilities.bank.investments import create_french_liquidity
from woob.capabilities.base import Currency
from woob.capabilities.bank import Account

from dateutil.relativedelta import relativedelta

from .pages import (
    LoginPage, AccountsPage, AccountDetailsPage,
    InvestmentPage, HistoryPage, MarketOrdersPage,
)


class URLWithDate(URL):
    def go(self, fromDate, toDate=None, *args, **kwargs):
        toDate_ = toDate or datetime.datetime.now().strftime('%d/%m/%Y')
        return super(URLWithDate, self).go(
            toDate=toDate_,
            fromDate=fromDate,
            accountId=self.browser.intAccount,
            sessionId=self.browser.sessionId,
        )


class DegiroBrowser(LoginBrowser):
    BASEURL = 'https://trader.degiro.nl'

    TIMEOUT = 60  # Market orders queries can take a long time

    login = URL(r'/login/secure/login', LoginPage)
    client = URL(r'/pa/secure/client\?sessionId=(?P<sessionId>.*)', LoginPage)
    product = URL(r'/product_search/secure/v5/products/info\?sessionId=(?P<sessionId>.*)', InvestmentPage)
    accounts = URL(
        r'/trading(?P<staging>\w*)/secure/v5/update/(?P<accountId>.*);jsessionid=(?P<sessionId>.*)\?historicalOrders=0' +
        r'&orders=0&portfolio=0&totalPortfolio=0&transactions=0&alerts=0&cashFunds=0&currencyExchange=0&',
        AccountsPage
    )
    account_details = URL(
        r'https://trader.degiro.nl/trading(?P<staging>\w*)/secure/v5/account/info/(?P<accountId>.*);jsessionid=(?P<sessionId>.*)',
        AccountDetailsPage
    )
    transaction_investments = URLWithDate(
        r'/reporting/secure/v4/transactions\?fromDate=(?P<fromDate>.*)' +
        '&groupTransactionsByOrder=false&intAccount=(?P<accountId>.*)' +
        '&orderId=&product=&sessionId=(?P<sessionId>.*)' +
        '&toDate=(?P<toDate>.*)',
        HistoryPage
    )
    history = URLWithDate(
        r'/reporting/secure/v4/accountoverview\?fromDate=(?P<fromDate>.*)' +
        '&groupTransactionsByOrder=false&intAccount=(?P<accountId>.*)' +
        '&orderId=&product=&sessionId=(?P<sessionId>.*)&toDate=(?P<toDate>.*)',
        HistoryPage
    )
    market_orders = URLWithDate(
        r'/reporting/secure/v4/order-history\?fromDate=(?P<fromDate>.*)' +
        '&toDate=(?P<toDate>.*)&intAccount=(?P<accountId>.*)&sessionId=(?P<sessionId>.*)',
        MarketOrdersPage
    )

    def __init__(self, *args, **kwargs):
        super(DegiroBrowser, self).__init__(*args, **kwargs)

        self.intAccount = None
        self.name = None
        self.sessionId = None
        self.account = None
        self.invs = {}
        self.trs = {}
        self.products = {}

    def do_login(self):
        try:
            self.login.go(data=json.dumps({'username': self.username, 'password': self.password}))
        except ClientError as e:
            if e.response.status_code == 400:
                raise BrowserIncorrectPassword()
            elif e.response.status_code == 403:
                error = e.response.json().get('statusText', '')
                if error == 'accountBlocked':
                    raise BrowserIncorrectPassword('Your credentials are invalid and your account is currently blocked.')
                raise Exception('Login failed with error: "%s".', error)
            raise

        self.sessionId = self.page.get_session_id()

        self.client.go(sessionId=self.sessionId)

        self.intAccount = self.page.get_information('intAccount')
        self.name = self.page.get_information('displayName')

    @need_login
    def iter_accounts(self):
        if self.account is None:
            staging = '_s' if 'staging' in self.sessionId else ''
            self.accounts.stay_or_go(staging=staging, accountId=self.intAccount, sessionId=self.sessionId)
            self.account = self.page.get_account()
            # Go to account details to fetch the right currency
            self.account_details.stay_or_go(staging=staging, accountId=self.intAccount, sessionId=self.sessionId)
            self.account.currency = self.page.get_currency()
            # Account balance is the sum of investments valuations
            self.account.balance = sum(inv.valuation.quantize(Decimal('0.00')) for inv in self.iter_investment(self.account))
        yield self.account

    @need_login
    def iter_investment(self, account):
        if account.id not in self.invs:
            staging = '_s' if 'staging' in self.sessionId else ''
            self.accounts.stay_or_go(staging=staging, accountId=self.intAccount, sessionId=self.sessionId)
            raw_invests = list(self.page.iter_investment(currency=account.currency))
            # Some invests are present twice. We need to combine them into one, as it's done on the website.
            invests = {}
            for raw_inv in raw_invests:
                if raw_inv.label not in invests:
                    invests[raw_inv.label] = raw_inv
                else:
                    invests[raw_inv.label].quantity += raw_inv.quantity
                    invests[raw_inv.label].valuation += raw_inv.valuation
            # Replace as liquidities investments that are cash
            self.invs[account.id] = [
                create_french_liquidity(inv.valuation) if len(inv.label) < 4 and Currency.get_currency(inv.label)
                else inv for inv in invests.values()
            ]
        return self.invs[account.id]

    @need_login
    def iter_market_orders(self, account):
        if account.type not in (Account.TYPE_MARKET, Account.TYPE_PEA):
            return

        # We can fetch up to 3 months of history (minus one day), older than that the JSON response is empty
        # We must fetch market orders 2 weeks at a time because if we fetch too many orders at a time the API crashes
        to_date = datetime.datetime.now()
        oldest = (to_date - relativedelta(months=3) + relativedelta(days=1))
        from_date = (to_date - relativedelta(weeks=2))

        while to_date > oldest:
            self.market_orders.go(fromDate=from_date.strftime('%d/%m/%Y'), toDate=to_date.strftime('%d/%m/%Y'))
            # Market orders are displayed chronogically so we must reverse them
            for market_order in sorted(self.page.iter_market_orders(), reverse=True, key=lambda order: order.date):
                yield market_order

            to_date = from_date - relativedelta(days=1)
            from_date = max(
                oldest,
                to_date - relativedelta(weeks=2),
            )

    @need_login
    def iter_history(self, account):
        if account.id not in self.trs:
            fromDate = (datetime.datetime.now() - relativedelta(years=1)).strftime('%d/%m/%Y')

            self.transaction_investments.go(fromDate=fromDate)

            self.fetch_products(list(self.page.get_products()))

            transaction_investments = list(self.page.iter_transaction_investments())
            self.history.go(fromDate=fromDate)

            # the list can be pretty big, and the tr list too
            # avoid doing O(n*n) operation
            trinv_dict = {(inv.code, inv._action, inv._datetime): inv for inv in transaction_investments}

            trs = list(self.page.iter_history(transaction_investments=NoCopy(trinv_dict), account_currency=account.currency))
            self.trs[account.id] = trs
        return self.trs[account.id]

    def fetch_products(self, ids):
        ids = list(set(ids) - set(self.products.keys()))
        if ids:
            page = self.product.open(
                json=ids,
                sessionId=self.sessionId,
            )
            self.products.update(page.get_products())

    def get_product(self, id):
        if id not in self.products:
            self.fetch_products([id])
        return self.products[id]


class NoCopy(object):
    # params passed to a @method are deepcopied, in each iteration of ItemElement
    # so we want to avoid repeatedly copying objects since we don't intend to modify them

    def __init__(self, v):
        self.v = v

    def __deepcopy__(self, memo):
        return self
