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

import time

from weboob.browser import LoginBrowser, URL
from weboob.tools.capabilities.bank.transactions import sorted_transactions

from .pages import (
    PortfolioPage, NewWebsiteFirstConnectionPage,
    AccountCodesPage, HistoryAPIPage,
)


def get_timestamp():
    return '{}'.format(int(time.time() * 1000))  # in milliseconds


class LinebourseAPIBrowser(LoginBrowser):
    BASEURL = 'https://www.offrebourse.com'

    new_website_first = URL(r'/rest/premiereConnexion', NewWebsiteFirstConnectionPage)
    account_codes = URL(r'/rest/compte/liste/vide/0', AccountCodesPage)

    # The API works with an encrypted account_code that starts with 'CRY'
    portfolio = URL(r'/rest/portefeuille/(?P<account_code>CRY[\w\d]+)/vide/true/false', PortfolioPage)
    history = URL(r'/rest/historiqueOperations/(?P<account_code>CRY[\w\d]+)/(?P<month_idx>\d+)/7/1', HistoryAPIPage)

    def __init__(self, baseurl, *args, **kwargs):
        self.BASEURL = baseurl
        super(LinebourseAPIBrowser, self).__init__(username='', password='', *args, **kwargs)

    def get_account_code(self, account_id):
        # 'account_codes' is a JSON containing the id_contracts
        # of all the accounts present on the Linebourse space.
        params = {'_': get_timestamp()}
        self.account_codes.go(params=params)
        assert self.account_codes.is_here()
        return self.page.get_contract_number(account_id)

    def go_portfolio(self, account_id):
        account_code = self.get_account_code(account_id)
        return self.portfolio.go(account_code=account_code)

    def iter_investments(self, account_id):
        self.go_portfolio(account_id)
        assert self.portfolio.is_here()
        date = self.page.get_date()
        return self.page.iter_investments(date=date)

    def iter_history(self, account_id):
        account_code = self.get_account_code(account_id)
        # History available is up the 3 months.
        # For each month we have to pass the month index.
        transactions = []
        for month_idx in range(3):
            self.history.go(
                account_code=account_code,
                month_idx=month_idx,
                params={'_': get_timestamp()},  # timestamp is necessary
            )
            transactions.extend(self.page.iter_history())
        # Transactions from the JSON need to be correctly ordered
        return sorted_transactions(transactions)
