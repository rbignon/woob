# -*- coding: utf-8 -*-

# Copyright(C) 2016      Edouard Lambert
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
from lxml import etree
from io import StringIO

from woob.browser import LoginBrowser, URL, need_login
from woob.exceptions import BrowserIncorrectPassword, ActionNeeded
from woob.browser.exceptions import HTTPNotFound, ServerError
from woob.capabilities.bank import Account
from woob.tools.capabilities.bank.investments import create_french_liquidity

from .pages import (
    LoginPage, HomePage, AccountsPage, OldAccountsPage, HistoryPage,
    InvestmentPage, InvestDetailPage, InvestmentListPage, MarketOrdersPage,
    QuestionPage, ChangePassPage, LogonFlowPage, ViewPage, SwitchPage,
    HandlePasswordsPage, PostponePasswords, PersonalInfoPage,
)


class BinckBrowser(LoginBrowser):
    BASEURL = 'https://web.binck.fr'

    old_website_connection = False
    unique_account = False

    login = URL(r'/Logon', LoginPage)
    view = URL('/PersonIntroduction/Index', ViewPage)
    logon_flow = URL(r'/AmlQuestionnairesOverview/LogonFlow$', LogonFlowPage)

    personal_info = URL(r'/PersonalInformationLogin', PersonalInfoPage)

    account = URL(r'/PortfolioOverview/Index', AccountsPage)
    accounts = URL(r'/PersonAccountOverview/Index', AccountsPage)
    old_accounts = URL(r'/AccountsOverview/Index', OldAccountsPage)

    account_switch = URL('/Header/SwitchAccount', SwitchPage)
    home_page = URL(r'/$',
                    r'/Home/Index', HomePage)

    investment = URL(r'/PortfolioOverview/GetPortfolioOverview', InvestmentPage)
    investment_list = URL(r'PortfolioOverview$', InvestmentListPage)
    invest_detail = URL(r'/SecurityInformation/Get', InvestDetailPage)

    market_orders = URL(r'/HistoricOrdersOverview/HistoricOrders', MarketOrdersPage)

    history = URL(r'/TransactionsOverview/GetTransactions',
                  r'/TransactionsOverview/FilteredOverview', HistoryPage)
    questions = URL(r'/FDL_Complex_FR_Compte',
                    r'/FDL_NonComplex_FR_Compte',
                    r'FsmaMandatoryQuestionnairesOverview', QuestionPage)
    change_pass = URL(r'/ChangePassword/Index',
                      r'/EditSetting/GetSetting\?code=MutationPassword', ChangePassPage)
    handle_passwords = URL(r'/PersonalCredentials/Index', HandlePasswordsPage)
    postpone_passwords = URL(r'/PersonalCredentials/PostPone', PostponePasswords)

    def deinit(self):
        if self.page and self.page.logged:
            self.location('https://www.binck.fr/deconnexion-site-client')
        super(BinckBrowser, self).deinit()

    def do_login(self):
        self.login.go()
        self.page.login(self.username, self.password)

        if self.handle_passwords.is_here():
            if self.page.has_action_needed():
                # There is no detailed message, just a button with "Créer l'identifiant personnel"
                # that is created with javascript.
                raise ActionNeeded('Veuillez créer votre nouvel identifiant personnel sur le site.')

            token = self.page.get_token()
            self.postpone_passwords.go(headers=token, method='POST')
            self.home_page.go()

        if self.login.is_here():
            error = self.page.get_error()
            # The message for the second error is :
            # Vous ne pouvez plus vous servir de cet identifiant pour vous connecter,
            # Nous vous prions d'utiliser celui que vous avez récemment créé.
            if error and any((
                'mot de passe' in error,
                'Vous ne pouvez plus vous servir de cet identifiant' in error,
            )):
                raise BrowserIncorrectPassword(error)
            elif error and any((
                'Votre compte a été bloqué / clôturé' in error,
                'Votre compte est bloqué, veuillez contacter le Service Clients' in error,
            )):
                raise ActionNeeded(error)
            raise AssertionError('Unhandled behavior at login: error is "{}"'.format(error))

        if self.personal_info.is_here():
            message = self.page.get_message()
            if 'informations personnelles' in message:
                raise ActionNeeded(message)
            raise AssertionError('Unhandled behavior at login: message is "%s"' % message)

    @need_login
    def switch_account(self, account_id):
        self.accounts.stay_or_go()
        if self.accounts.is_here():
            token = self.page.get_token()
        data = {'accountNumber': account_id}
        # Important: the "switch" request without the token will return a 500 error
        self.account_switch.go(data=data, headers=token)
        # We should be automatically redirected to the accounts page:
        assert self.accounts.is_here(), 'switch_account did not redirect to AccountsPage properly'

    @need_login
    def iter_accounts(self):
        # If we already know that it is an old website connection,
        # we can call iter_old_accounts() right away.
        if self.old_website_connection:
            self.logger.warning('This connection has accounts on the old version of the website.')
            for account in self.iter_old_accounts():
                yield account
            return

        if self.unique_account:
            self.account.stay_or_go()
        else:
            self.accounts.stay_or_go()

        if self.page.has_accounts_table():
            for a in self.page.iter_accounts():
                a._invpage = None
                a._histpages = None

                self.switch_account(a.id)
                # We must get the new token almost everytime we get a new page:
                if self.accounts.is_here():
                    token = self.page.get_token()
                # Get valuation_diff from the investment page
                try:
                    data = {'grouping': 'SecurityCategory'}
                    a.valuation_diff = self.investment.go(data=data, headers=token).get_valuation_diff()
                except HTTPNotFound:
                    # if it is not an invest account, the portfolio link may be present but hidden and return a 404
                    a.valuation_diff = None
                yield a

        # Some Binck connections don't have any accounts on the new AccountsPage,
        # so we need to fetch them on the OldAccountsPage for now:
        else:
            self.old_website_connection = True
            for account in self.iter_old_accounts():
                yield account

    @need_login
    def iter_old_accounts(self):
        self.old_accounts.go()
        for a in self.page.iter_accounts():
            self.logger.warning('There is an old account: %s', a.label)
            try:
                self.old_accounts.stay_or_go().go_to_account(a.id)
            except ServerError as exception:
                # get html error to parse
                parser = etree.HTMLParser()
                html_error = etree.parse(StringIO(exception.response.text), parser)
                account_error = html_error.xpath('//p[contains(text(), "Votre compte est")]/text()')
                if account_error:
                    raise ActionNeeded(account_error[0])
                else:
                    raise

            a.iban = self.page.get_iban()
            # Get token
            token = self.page.get_token()
            # Get investment page
            data = {'grouping': "SecurityCategory"}
            try:
                a._invpage = self.investment.go(data=data, headers=token) \
                    if self.page.is_investment() else None
            except HTTPNotFound:
                # if it's not an invest account, the portfolio link may be present but hidden and return a 404
                a._invpage = None

            if a._invpage:
                a.valuation_diff = a._invpage.get_valuation_diff()
            # Get history page
            data = [('currencyCode', a.currency), ('startDate', ""), ('endDate', "")]
            a._histpages = [self.history.go(data=data, headers=token)]
            while self.page.doc['EndOfData'] is False:
                a._histpages.append(self.history.go(data=self.page.get_nextpage_data(data[:]), headers=token))

            yield a

    @need_login
    def iter_investment(self, account):
        if account.balance == 0:
            return
        # Start with liquidities:
        if account._liquidity:
            yield create_french_liquidity(account._liquidity)

        if self.old_website_connection:
            self.old_accounts.stay_or_go().go_to_account(account.id)
            if account._invpage:
                for inv in account._invpage.iter_investment(currency=account.currency):
                    if not inv.code:
                        params = {'securityId': inv._security_id}
                        self.invest_detail.go(params=params)
                        if self.invest_detail.is_here():
                            inv.code, inv.code_type = self.page.get_isin_code_and_type()
                    yield inv
            return

        self.switch_account(account.id)
        token = self.page.get_token()

        try:
            data = {'grouping': 'SecurityCategory'}
            self.investment.go(data=data, headers=token)
        except HTTPNotFound:
            return

        for inv in self.page.iter_investment(currency=account.currency):
            yield inv

    def go_to_market_orders(self, headers, page):
        data = {
            'year': str(datetime.datetime.now().year),
            'month': str(datetime.datetime.now().month),
            'page': str(page),
            'sortProperty': 'AccountOrderId',
            'sortOrder': '1',
        }
        self.market_orders.go(data=data, headers=headers)

    @need_login
    def iter_market_orders(self, account):
        if account.type not in (Account.TYPE_MARKET, Account.TYPE_PEA):
            # This account type has no market order
            return

        self.switch_account(account.id)
        headers = self.page.get_token()
        try:
            self.go_to_market_orders(headers, page=1)
        except HTTPNotFound:
            self.logger.warning('Account %s has no available market orders.', account.label)
            return

        # First market order page
        for order in self.page.iter_market_orders():
            yield order

        # Verify if there are other pages and handle pagination
        total_pages = self.page.count_total_pages()
        if total_pages > 1:
            for page in range(2, total_pages + 1):
                self.go_to_market_orders(headers, page)
                for order in self.page.iter_market_orders():
                    yield order

    @need_login
    def iter_history(self, account):
        if self.old_website_connection:
            if account._histpages:
                for page in account._histpages:
                    for tr in page.iter_history():
                        yield tr
            return

        self.switch_account(account.id)
        token = self.page.get_token()
        data = [('currencyCode', account.currency), ('startDate', ''), ('endDate', '')]
        history_pages = [self.history.go(data=data, headers=token)]
        while self.page.doc['EndOfData'] is False:
            history_pages.append(self.history.go(data=self.page.get_nextpage_data(data[:]), headers=token))

        for page in history_pages:
            for tr in page.iter_history():
                yield tr
