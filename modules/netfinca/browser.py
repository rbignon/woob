# -*- coding: utf-8 -*-

# Copyright(C) 2012-2019  Budget-Insight
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

from datetime import datetime

from dateutil.relativedelta import relativedelta

from weboob.browser import LoginBrowser, URL
from weboob.exceptions import BrowserUnavailable, ActionNeeded

from .pages import InvestmentsPage, AccountsPage, MarketOrdersPage


class NetfincaBrowser(LoginBrowser):
    accounts = URL(r'/netfinca-titres/servlet/com.netfinca.frontcr.synthesis.HomeSynthesis', AccountsPage)
    investments = URL(r'/netfinca-titres/servlet/com.netfinca.frontcr.account.WalletVal\?nump=(?P<nump_id>.*)', InvestmentsPage)
    market_orders = URL(r'/netfinca-titres/servlet/com.netfinca.frontcr.order.OrderList', MarketOrdersPage)

    def do_login(self):
        raise BrowserUnavailable()

    def iter_accounts(self):
        self.accounts.stay_or_go()
        self.check_action_needed()
        return self.page.iter_accounts()

    def check_action_needed(self):
        self.accounts.stay_or_go()
        message = self.page.get_action_needed_message()
        if 'merci de renseigner les informations' in message:
            # Customers have to fill their e-mail address and phone number
            raise ActionNeeded(message)

    def iter_investments(self, account):
        self.accounts.stay_or_go()

        nump_id = self.page.get_nump_id(account)
        self.investments.go(nump_id=nump_id)

        for invest in self.page.get_investments(account_currency=account.currency):
            yield invest

        liquidity = self.page.get_liquidity()
        if liquidity:
            yield liquidity

    def is_account_present(self, account_id):
        # This method is used by parent modules with several perimeters
        # and therefore several Netfinca spaces to check that the requested
        # account is present on the current Netfinca space.
        self.accounts.stay_or_go()
        return self.page.is_account_present(account_id)

    def go_to_market_orders(self, page, from_date, to_date):
        data = {
            'ORDER_STATUS': 'NONE',
            'ORDER_UPDDTMIN': from_date,
            'ORDER_UPDDTMAX': to_date,
            'PRODUCT_ID': '',
            'ORDER_LIST_OPERATION_TYPE_ALL': '1',
            'ORDER_TYPE': 'UNKNOWN',
            'save': 'false',
            'sensTri': '-',
            'champsTri': 'LAST_MKT_IMPACT',
            'PAGE': str(page),
            'expandCriterias': 'true',
        }
        self.market_orders.go(data=data)

    def iter_market_orders(self, account):
        self.accounts.stay_or_go()
        # First go to the investment details of the right account
        nump_id = self.page.get_nump_id(account)
        self.investments.go(nump_id=nump_id)
        # Then access account market orders with 6 months of history
        date_format = '%d/%m/%Y'
        today = datetime.today()
        to_date = today.strftime(date_format)
        from_date = (today - relativedelta(months=6)).strftime(date_format)
        # First page
        self.go_to_market_orders(1, from_date, to_date)
        if self.page.has_no_order():
            return
        for order in self.page.iter_market_orders():
            if order._details_link:
                self.location(order._details_link)
                self.page.fill_market_order(obj=order)
            yield order

        # Handle pagination
        next_pages = self.page.get_next_pages()
        if next_pages:
            for page in next_pages:
                self.go_to_market_orders(page, from_date, to_date)
                for order in self.page.iter_market_orders():
                    yield order
