# Copyright(C) 2022      Budget Insight
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

from base64 import b64encode
import time
import random
import string

from woob.browser.browsers import URL, need_login
from woob.browser.mfa import TwoFactorBrowser
from woob.browser.exceptions import ClientError
from woob.exceptions import BrowserIncorrectPassword, BrowserUserBanned
from woob.capabilities.bank import Account

from .pages import (
    HomePage, KeypadPage, MonEspaceHome, PreHomePage,
    RedirectMonEspaceHome, RedirectionPage, LoginPage, AggregationPage,
    AccountsPage, CardsPage, LifeInsurancesPage, LoansPage, LoanDetailsPage,
    TransactionsPage, CardTransactionsPage, TransactionDetailsPage,
)


class MonEspaceBrowser(TwoFactorBrowser):
    BASEURL = 'https://monespace.lcl.fr'

    keypad = URL(r'/api/login/keypad', KeypadPage)
    login = URL(r'/api/login', LoginPage)
    login_contract = URL(r'/api/login/contract')
    user_contract = URL(r'/api/user/contract')
    launch_redirection = URL(
        r'https://particuliers.secure.lcl.fr/outil/UAUT/warbel-context-provider',
    )
    redirection = URL(r'https://particuliers.secure.lcl.fr/outil/UAUT/Contract/redirection', RedirectionPage)

    pre_home = URL(r'https://particuliers.secure.lcl.fr/outil/UWER/Accueil/majicER', PreHomePage)
    home = URL(r'https://particuliers.secure.lcl.fr/outil/UWHO/Accueil/', HomePage)

    redirect_monespace_home = URL(
        r'https://particuliers.secure.lcl.fr/outil/UAUT/acces_refonte\?xtatc=INT-937',
        RedirectMonEspaceHome
    )
    monespace_home = URL(r'/connexion/legacy', MonEspaceHome)
    aggregation = URL(r'/api/user/accounts/aggregation\?contract_id=(?P<contracts_id>.*)', AggregationPage)

    accounts = URL(
        r'/api/user/accounts\?type=current&contract_id=(?P<contracts_id>.*)&is_eligible_for_identity=false&include_aggregate_account=(?P<is_enrolled>.*)',
        AccountsPage
    )
    savings = URL(
        r'/api/user/accounts\?type=saving&contract_id=(?P<contracts_id>.*)&is_eligible_for_identity=false&include_aggregate_account=(?P<is_enrolled>.*)',
        AccountsPage
    )
    cards = URL(
        r'/api/user/cards/deferred\?contract_id=(?P<contracts_id>.*)&include_aggregation=(?P<is_enrolled>.*)',
        CardsPage
    )
    life_insurances = URL(
        r'/api/user/accounts/life_insurances\?contract_id=(?P<contracts_id>.*)&include_aggregate_account=(?P<is_enrolled>.*)',
        LifeInsurancesPage
    )
    loans = URL(
        r'/api/user/loans\?contract_id=(?P<contracts_id>.*)&include_aggregate_loan=(?P<is_enrolled>.*)',
        LoansPage
    )
    loan_details = URL(
        r'https://monespace.lcl.fr/api/user/loans/(?P<loan_id>.*)\?source_code=(?P<source_code>.*)&product_code=(?P<product_code>.*)&branch=(?P<branch>.*)&account=(?P<account>.*)&is_aggregate_loan=(?P<is_enrolled>.*)&contract_id=(?P<contracts_id>.*)',
        LoanDetailsPage
    )
    revolvings = URL(r'api/user/loans/revolving\?contract_id=(?P<contracts_id>.*)&include_aggregate_loan=(?P<is_enrolled>.*)')

    transactions = URL(
        r'/api/user/accounts/(?P<account_id>.*)/transactions\?contract_id=(?P<contracts_id>.*)&range=0-99',
        TransactionsPage
    )
    transaction_details = URL(
        r'https://monespace.lcl.fr/api/user/accounts/(?P<account_id>.*)/transactions/(?P<transaction_id>.*)\?contract_id=(?P<contracts_id>.*)',
        TransactionDetailsPage
    )
    cards_transactions = URL(
        r'/api/user/cards/(?P<card_id>.*)/transactions\?contract_id=(?P<contracts_id>.*)',
        CardTransactionsPage
    )
    comings = URL(r'/api/user/accounts/sepa/debits\?contract_id=(?P<contracts_id>.*)&account_id=(?P<account_id>.*)&number_of_days=14&range=0-99')

    __states__ = ('session_id', 'contract_id', 'encoded_contract_id', 'user_name')

    def __init__(self, config, *args, **kwargs):
        super(MonEspaceBrowser, self).__init__(config, *args, **kwargs)
        self.session_id = ''.join(random.choices(string.digits, k=29))

    def do_login(self):
        self.keypad.go()

        try:
            self.login.go(
                json={
                    'callingUrl': '/connexion',
                    'clientTimestamp': round(time.time() * 1000),
                    'encryptedIdentifier': False,
                    'identifier': self.username,
                    'keypad': self.page.encode_password(self.password),
                    'sessionId': self.session_id,
                },
            )
        except ClientError as e:
            if e.response.status_code == 401:
                code, message = LoginPage(self, e.response).get_error()
                if code == 'INVALID_USER_ID':
                    raise BrowserIncorrectPassword(bad_fields=['login'])
                if code == 'BAD_CREDENTIALS':
                    raise BrowserIncorrectPassword(bad_fields=['password'])
                if code == 'BAD_CREDENTIALS_AND_TEMPORARY_BLOCKING':
                    raise BrowserUserBanned()
                raise AssertionError(f'Unhandled error code during login. code:{code}, message:{message}')
            raise AssertionError('Unhandled error during login')

        (
            self.token, self.refresh_token, self.expire_date, self.encrypted_expire_date, self.redirect_user_id,
        ) = self.page.get_authentication_data()
        self.session.headers['X-Authorization'] = f'Bearer {self.token}'
        self.contract_id = self.page.get_contract_id()
        self.encoded_contract_id = self.encode_contract(self.contract_id)
        self.user_name = self.page.get_user_name()

        self.login_contract.go(
            json={
                'clientTimestamp': round(time.time() * 1000),
                'contractId': self.contract_id,
            },
        )
        self.user_contract.go(
            json={
                'type': 'CLI',
                'id': self.contract_id,
            },
        )

        self.go_legacy_website()

        self.redirect_monespace_home.go()
        assert self.monespace_home.is_here(), 'expected to be in monespace_home'

        self.aggregation.go(contracts_id=self.encoded_contract_id)
        self.is_enrolled = self.page.is_enrolled()

    @need_login
    def iter_accounts(self):
        checking_accounts = []
        self.accounts.go(contracts_id=self.encoded_contract_id, is_enrolled=self.is_enrolled)
        for account in self.page.iter_accounts(user_name=self.user_name):
            checking_accounts.append(account)
            yield account

        self.savings.go(contracts_id=self.encoded_contract_id, is_enrolled=self.is_enrolled)
        yield from self.page.iter_accounts(user_name=self.user_name)

        self.cards.go(contracts_id=self.encoded_contract_id, is_enrolled=self.is_enrolled)
        for card in self.page.iter_cards(user_name=self.user_name):
            # find parent
            for account in checking_accounts:
                if account._internal_id == card._parent_internal_id:
                    card.parent = account
                    break
            yield card

        self.life_insurances.go(contracts_id=self.encoded_contract_id, is_enrolled=self.is_enrolled)
        yield from self.page.iter_accounts(user_name=self.user_name)

        self.loans.go(contracts_id=self.encoded_contract_id, is_enrolled=self.is_enrolled)
        for loan in self.page.iter_loans():
            # find the loan's parent
            for account in checking_accounts:
                if account.id == loan._parent_id:
                    loan.parent = account
                    break

            # fill the loan's details
            self.loan_details.go(
                loan_id=loan.id,
                source_code=loan._source_code,
                product_code=loan._product_code,
                branch=loan._branch,
                account=loan._account,
                contracts_id=self.encoded_contract_id,
                is_enrolled=self.is_enrolled,
            )
            self.page.fill_loan(obj=loan)
            yield loan

    @need_login
    def iter_history(self, account):
        # TODO: implement comings

        if account.type not in (Account.TYPE_CHECKING, Account.TYPE_SAVINGS, Account.TYPE_PEA, Account.TYPE_CARD):
            return

        if account.type == Account.TYPE_CARD:
            self.cards_transactions.go(card_id=account.id, contracts_id=self.encoded_contract_id)
            yield from self.page.iter_transactions()
            return

        self.transactions.go(
            account_id=account._internal_id,
            contracts_id=self.encoded_contract_id,
        )
        for tr in self.page.iter_transactions():
            if tr._details_available:
                self.transaction_details.go(
                    account_id=account._internal_id,
                    contracts_id=self.encoded_contract_id,
                    transaction_id=tr.id
                )
                self.page.fill_transaction(obj=tr)
            yield tr

    def go_legacy_website(self):
        self.launch_redirection.go(
            params={
                'token': self.token,
                'rt': self.refresh_token,
                'exp': self.encrypted_expire_date,
                'ib': self.redirect_user_id,
            },
        )

        assert self.redirection.is_here(), 'expected to be in redirection'
        self.page.go_pre_home()

        assert self.pre_home.is_here(), 'expected to be in pre_home'
        self.page.go_home()

        assert self.home.is_here(), 'expected to be in home'

    @staticmethod
    def encode_contract(contract_id):
        return b64encode(contract_id.encode('ascii')).decode('ascii')[:-2]
