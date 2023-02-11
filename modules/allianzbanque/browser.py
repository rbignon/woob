# -*- coding: utf-8 -*-

# Copyright(C) 2012-2022  Budget Insight
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

from datetime import date

from dateutil.relativedelta import relativedelta

from woob.browser import URL, need_login
from woob.browser.browsers import AbstractBrowser, ClientError, ServerError
from woob.capabilities.bank import Account
from woob.tools.decorators import retry

from .pages import (
    AccountsPage, ProfilePage, ContractsPage, LoansPage,
    CypherPage, MarketPage, InvestmentsPage,
)


__all__ = ['AllianzbanqueBrowser']


class AllianzbanqueBrowser(AbstractBrowser):
    PARENT = 'cmso'
    PARENT_ATTR = 'package.par.browser.CmsoParBrowser'
    BASEURL = 'https://api.allianzbanque.fr'

    # needed fo CMSO
    redirect_uri = 'https://mon.allianzbanque.fr/auth/checkuser'
    error_uri = 'https://mon.allianzbanque.fr/auth/errorauthn'
    client_uri = 'com.arkea.azb.rwd'
    name = 'azb'
    arkea = 'B1'
    arkea_si = '0B1'
    arkea_client_id = 'FtzkRLIR3TurVkG4vzbbGxnyrTu0w2I8'
    original_site = 'https://mon.allianzbanque.fr'

    accounts = URL(r'/distri-account-api/api/v1/persons/me/accounts', AccountsPage)
    balances = URL(
        r'/distri-account-api/api/v1/persons/me/accounts/(?P<account_id>[A-Z0-9]{10})/balances$',
        AccountsPage
    )
    balances_comings = URL(
        r'/distri-account-api/api/v1/persons/me/accounts/(?P<account_id>[A-Z0-9]{10})/total-upcoming-transactions',
        AccountsPage
    )
    transactions = URL(
        r'/distri-account-api/api/v1/persons/me/accounts/(?P<account_id>[A-Z0-9]{10})/transactions',
        AccountsPage
    )
    transactions_comings = URL(
        r'/distri-account-api/api/v1/persons/me/accounts/(?P<account_id>[A-Z0-9]{10})/upcoming-transactions',
        AccountsPage
    )
    life_insurances = URL(r'/savingsb2bapi/api/v1/contractslist')
    life_insurances_details = URL(r'/savingsb2bapi/api/v1/contractdetails/(?P<contract>.*)', ContractsPage)
    loans = URL(r'/creditpartapi/api/v1//management-loans\?loanTypes=REAL_ESTATE,CONSUMER', LoansPage)
    profile = URL(r'/personapi/api/v2/clients/me/infos', ProfilePage)

    market_cypher = URL(
        r'/cypher-api/cypher\?service=bourse&contractNumber=(?P<account_id>[A-Z0-9]{10})',
        CypherPage
    )
    market = URL(
        r'https://www.bourse.allianzbanque.fr/ariane/webact/WebBank/scripts/AGF/login.jsp\?cypher=(?P<cypher>.*)',
        MarketPage
    )
    investments = URL(r'https://www.bourse.allianzbanque.fr/ariane/secure_ajax/(?P<page>\w+).html', InvestmentsPage)

    def __init__(self, *args, **kwargs):
        # most of url return 403 without this origin header
        kwargs['origin'] = self.original_site
        super(AllianzbanqueBrowser, self).__init__(*args, **kwargs)

    def get_tpp_headers(self, data=''):
        return {'X-ARKEA-EFS': self.arkea}

    def get_pkce_codes(self):
        # Switched from parent CMSO
        # This quality website uses verifier as a challenge, and vice-versa
        # They will put it right in the future as they did for the rest of CMSO modules
        # TODO delete this function when they do
        verifier = self.code_verifier()
        return self.code_challenge(verifier), verifier

    def refresh_access_token(self):
        self.spaces.go(json={'includePart': True})
        self.change_space.go(json={
            'clientIdSource': self.arkea_client_id,
            'espaceDestination': 'PART',
            'fromMobile': False,
            'numContractDestination': self.page.get_part_space(),
        })

        access_token = self.page.get_access_token()
        self.session.headers['Authorization'] = 'Bearer %s' % access_token
        self.session.headers['X-Csrf-Token'] = access_token

    @need_login
    def iter_accounts(self):
        # Using CMSO iter_accounts will work very partially,
        # only for checkings/savings, and with important changes in Pages.
        # Instead we call for Allianzbanque own intern API.
        # Content is close, but not equal to PSAbanqe own API,
        # So Pages are not abstracted from PSA.

        # CMSO attribute
        if self.accounts_list:
            return self.accounts_list

        # Same as CMSO : this step is necessary to get a token that is also valid for the market space.
        self.refresh_access_token()

        # 1. get all checking and savings
        go_accounts = retry(ClientError, tries=5)(self.accounts.go)
        go_accounts(params={'types': 'CHECKING,SAVING'})
        for account in self.page.iter_accounts():
            self.balances.go(account_id=account.id)
            self.page.fill_balance(account)
            date_to = (date.today() + relativedelta(months=1)).strftime('%Y-%m-%dT00:00:00.000Z')
            self.balances_comings.go(account_id=account.id, params={'dateTo': date_to})
            self.page.fill_coming(account)
            self.accounts_list.append(account)

        # 2. get life_insurances accounts
        page = self.life_insurances.go().json()
        # those ids are not persistent
        contracts = [
            contract['cryptedContractNumber']
            for contract in page
        ]
        for contract in contracts:
            self.life_insurances_details.go(contract=contract)
            con = self.page.get_contract()
            if con:
                self.accounts_list.append(con)

        # 3. get loans
        owner_name = self.get_profile().name.upper()
        self.loans.go()
        for loan in self.page.iter_loans(name=owner_name):
            self.accounts_list.append(loan)

        return self.accounts_list

    @need_login
    def iter_history(self, account):
        if account.type in (Account.TYPE_LOAN, Account.TYPE_LIFE_INSURANCE):
            return []

        if account.type in (Account.TYPE_MARKET, Account.TYPE_PEA):
            try:
                self.market_cypher.go(account_id=account.id)
                cypher = self.page.get_cypher()
                self.market.go(cypher=cypher)
                self.investments.go(page="histoMouv")
                return self.page.iter_history()
            finally:
                # Needed to come back from the market space
                self.refresh_access_token()

        go_transactions = retry((ClientError, ServerError), tries=5)(self.transactions.go)
        go_transactions(account_id=account.id)
        return self.page.iter_transactions()

    @need_login
    def iter_coming(self, account):
        if account.type not in (Account.TYPE_CHECKING, Account.TYPE_SAVINGS):
            return

        date_to = (date.today() + relativedelta(months=3)).strftime('%Y-%m-%dT00:00:00.000Z')
        go_transactions_comings = retry((ServerError), tries=5)(self.transactions_comings.go)
        go_transactions_comings(account_id=account.id, params={'dateTo': date_to})
        for coming in self.page.iter_comings():
            yield coming

    @need_login
    def iter_investment(self, account):
        if account.type not in (Account.TYPE_MARKET, Account.TYPE_PEA):
            return []

        try:
            self.market_cypher.go(account_id=account.id)
            cypher = self.page.get_cypher()
            self.market.go(cypher=cypher)

            self.investments.go(page='synthesis', method='POST')
            vdate = self.page.get_vdate()
            investments = []

            # Include liquidities for PEA only: positive liquidities also mentioned
            # on the website for "compte titres" but the problem is that the
            # balance is already equal to the sum of its invesments' valuations.
            # Including liquidities for "comptes titres" would result in inconsistencies
            # (two different balances).
            if account.type == Account.TYPE_PEA:
                liquidity = self.page.get_liquidity()
                if liquidity:
                    investments.append(liquidity)

            self.investments.go(page='valorisation', method='POST')
            for investment in self.page.iter_investment(vdate=vdate):
                investments.append(investment)
            return investments
        finally:
            # Needed to come back from the market space
            self.refresh_access_token()
