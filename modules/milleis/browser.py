# Copyright(C) 2022-2023 Powens
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

from hashlib import sha256
from base64 import b16encode
from datetime import datetime
from random import choice
from re import match
import string
from urllib.parse import quote_plus

from dateutil.relativedelta import relativedelta

from woob.browser import LoginBrowser, URL, need_login
from woob.browser.exceptions import ClientError
from woob.exceptions import BrowserIncorrectPassword, BrowserUserBanned, ActionNeeded, ActionType
from woob.capabilities.bank import Account
from woob.tools.capabilities.bank.transactions import sorted_transactions

from .document_pages import DocumentsPage, PdfPage
from .pages import (
    AccountsHistoryPage, AuthPage, CardsHistoryPage, CardsPage, CheckingAccountsPage,
    GetMarketURLPage, TokenPage, LifeInsuranceAccountsPage, LifeInsuranceHistoryPage,
    LoanAccountsPage, MarketAccountsPage, MarketHistoryPage, MarketInvestPage,
    SavingAccountsPage, GetProfilePage, UserStatesPage, LoanAccountsDetailsPage,
)


class MilleisBrowser(LoginBrowser):
    BASEURL = 'https://api-gw.milleis.fr'

    auth_page = URL(r'/auth/authorize', AuthPage)
    token_page = URL(r'/auth/token', TokenPage)

    user_states_page = URL(r'/user-states/v1/(?P<user_id>)', UserStatesPage)

    card_accounts_page = URL(r'/accounts/secured/cards$', CardsPage)
    cards_history_page = URL(
        r'/accounts/secured/cards/(?P<card_history_id>.*)/movements',
        CardsHistoryPage
    )

    checking_accounts_page = URL(r'/accounts/secured/current-accounts', CheckingAccountsPage)
    saving_accounts_page = URL(r'/accounts/secured/saving-accounts', SavingAccountsPage)
    accounts_history_page = URL(
        r'/accounts/secured/accounts/(?P<account_history_id>.*)/movements',
        AccountsHistoryPage
    )

    market_accounts_page = URL(r'/accounts/secured/security-accounts', MarketAccountsPage)
    get_market_url_page = URL(r'/accounts/secured/trading-url', GetMarketURLPage)
    market_invest_page = URL(r'https://bourse.milleis.fr/milleis/trading/positions/realtime', MarketInvestPage)
    market_history_page = URL(r'https://bourse.milleis.fr/milleis/trading/movements/security', MarketHistoryPage)

    life_insurance_accounts_page = URL(
        r'/accounts/secured/life-insurances$',
        LifeInsuranceAccountsPage
    )
    life_insurance_history_page = URL(
        r'/accounts/secured/life-insurances/(?P<life_insurance_id>)',
        LifeInsuranceHistoryPage
    )

    loan_accounts_page = URL(r'/accounts/secured/loans$', LoanAccountsPage)
    loan_accounts_details_page = URL(
        r'/accounts/secured/loans/(?P<loan_details_id>.*)/details',
        LoanAccountsDetailsPage
    )

    profile_page = URL(r'/contacts/v1/(?P<user_id>)', GetProfilePage)

    documents_download = URL(r'/documents/secured/documents/download', PdfPage)
    documents_page = URL(r'/documents/secured/documents', DocumentsPage)

    TIMEOUT = 30

    def code_verifier(self):
        # code_verifier and code_challenger logic found in
        # https://client.milleis.fr/mnetfront/main-es2015.f5f15d4b5efee86005d8.js
        # Fake base36 string made of random characters works
        # No need to mimic the real JS so far
        base_36_char = string.digits + string.ascii_lowercase
        code_verifier = ''
        for _ in range(6):
            code_verifier += choice(base_36_char)
        return code_verifier

    def code_challenger(self, verifier):
        code_challenger = sha256(verifier.encode('utf-8')).digest()
        code_challenger = b16encode(code_challenger).lower()
        return code_challenger

    def build_timestamp(self, relative_delta=None):
        # History pages for some accounts need a timestamp
        # to define the time interval of the result
        # We get wrong dates or an empty JSON if the "microsecond" parameter
        # is not set to 1000 so that it matches 13 digits timestamps
        dt = datetime.now()
        if relative_delta:
            dt += relative_delta
        data_date = datetime.timestamp(dt.replace(microsecond=1000))
        return str(data_date).replace('.', '')

    def do_login(self):
        code_verifier = self.code_verifier()
        code_challenger = self.code_challenger(code_verifier)

        data = {
            'login': self.username,
            'password': self.password,
            'codeChallenger': code_challenger,
            'tempVersion': 'v2',
        }

        old_username = match(r'\d{6}[a-zA-Z]{2}', self.username)
        if old_username:
            # No usable response from the API, message is generated by JS
            raise ActionNeeded(
                locale="fr-FR", message="Veuillez contacter votre Banquier Privé afin qu'il vous transmette vos nouveaux identifiants.",
                action_type=ActionType.CONTACT,
            )

        try:
            self.auth_page.go(json=data)
        except ClientError as e:
            if e.response.status_code == 401:
                raise BrowserIncorrectPassword()
            if e.response.status_code == 423:
                raise BrowserUserBanned()
            raise

        self.token_page.go(json={'codeVerifier': code_verifier})
        self.session.headers['Authorization'] = self.page.get_token()

        self.user_states_page.go(user_id=self.username[1:])
        if self.page.is_strong_auth_required():
            raise ActionNeeded(
                locale="fr-FR", message="Vous devez réaliser une authentification forte sur le portail internet.",
                action_type=ActionType.PERFORM_MFA,
            )

    @need_login
    def iter_accounts(self):
        # We can't know which types of accounts are present for a
        # given connexion. The website does the same thing, it asks the API
        # for every possible route and returns an empty list if there are no
        # accounts on the specific route
        accounts = []
        accounts_pages = [
            self.card_accounts_page,
            self.checking_accounts_page,
            self.saving_accounts_page,
            self.market_accounts_page,
            self.life_insurance_accounts_page,
            self.loan_accounts_page,
        ]

        for accounts_page in accounts_pages:
            accounts_page.go()
            if accounts_page is self.loan_accounts_page:
                for account in self.page.iter_accounts():
                    self.loan_accounts_details_page.go(loan_details_id=account._loan_details_id)
                    self.page.fill_loan(obj=account)
                    accounts.extend([account])
            else:
                accounts.extend(self.page.iter_accounts())
            if accounts_page is self.market_accounts_page:
                accounts.extend(self.page.iter_cash_accounts())

        return accounts

    @need_login
    def iter_history(self, account):
        start_date = self.build_timestamp(relativedelta(years=-1))
        end_date = self.build_timestamp()

        if account.type == Account.TYPE_CARD:
            data = {
                'id': account._reference,
                'root': account._root,
                'startDate': start_date,
                'endDate': end_date,
            }
            self.cards_history_page.go(card_history_id=account._reference, params=data)
            return self.page.iter_history()

        # _is_cash attribute needed to differentiate accounts having the same type
        # but not the same method for fetching history or investment. For example,
        # "Espèces PEA" and "Comptes PEA Géré"
        if account._is_cash is False and account.type in (Account.TYPE_MARKET, Account.TYPE_PEA):
            self.get_market_url_page.go(params={'account': quote_plus(account.number)})
            iter_history_url = self.page.get_iter_history_url()
            self.location(iter_history_url)
            self.market_history_page.go()
            return sorted_transactions(self.page.iter_history())

        if account.type in (
            Account.TYPE_CHECKING,
            Account.TYPE_SAVINGS,
            Account.TYPE_MARKET,
            Account.TYPE_PEA,
        ):
            self.accounts_history_page.go(
                account_history_id=account._iter_history_id,
                params={
                    'id': account._iter_history_id,
                    'startDate': start_date,
                    'endDate': end_date,
                },
            )
            return sorted_transactions(self.page.iter_history())

        return []

    @need_login
    def iter_investments(self, account):
        if account.type == Account.TYPE_LIFE_INSURANCE:
            self.life_insurance_history_page.go(life_insurance_id=account.id)
            return self.page.iter_investments()

        if account._is_cash is False and account.type in (Account.TYPE_MARKET, Account.TYPE_PEA):
            self.get_market_url_page.go(params={'account': quote_plus(account.number)})
            iter_invest_url = self.page.get_iter_invest_url()
            self.location(iter_invest_url)
            return self.page.iter_investments()

        return []

    @need_login
    def get_profile(self):
        self.profile_page.go(user_id=self.username[1:])
        return self.page.get_profile()

    @need_login
    def iter_subscriptions(self):
        self.profile_page.go(user_id=self.username[1:])
        yield self.page.get_subscription()

    @need_login
    def iter_documents(self, subscription):
        start_date = self.build_timestamp(relativedelta(months=-6))
        end_date = self.build_timestamp()
        params = {
            'start': start_date,
            'end': end_date,
        }
        self.documents_page.go(params=params)
        return self.page.iter_documents(subid=subscription.id)

    def download_document(self, document):
        data = {'documentId': document._download_id}
        return self.documents_download.open(json=data).content
