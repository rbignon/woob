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
from datetime import date
import re
import time
import random
import string

from dateutil.relativedelta import relativedelta

from woob.browser.browsers import URL, LoginBrowser, StatesMixin, need_login
from woob.browser.exceptions import ClientError, ServerError
from woob.capabilities.base import empty, find_object
from woob.exceptions import ActionNeeded, ActionType, BrowserIncorrectPassword, BrowserUserBanned
from woob.capabilities.bank import Account
from woob.tools.capabilities.bank.investments import create_french_liquidity
from woob.tools.decorators import retry

from .pages import (
    AVHistoryPage, AVInvestmentsPage, BourseHomePage, BoursePage, CardDetailsPage, CardSynthesisPage, DiscPage,
    NoPermissionPage, SEPAMandatePage, HomePage, KeypadPage,
    MonEspaceHome, PreHomePage, RedirectMonEspaceHome, RedirectionPage, LoginPage, AggregationPage,
    AccountsPage, CardsPage, LifeInsurancesPage, LoansPage, LoanDetailsPage, RoutagePage, GetContractPage,
    TermAccountsPage, TransactionsPage, CardTransactionsPage, LaunchRedirectionPage, DocumentsPage, CONTRACT_TYPES,
)


class LifeInsuranceUnreachable(Exception):
    # we failed to reach lifeinsurance's details. a retry is enough.
    pass


class LifeInsuranceNotAvailable(Exception):
    # we can not access the lifeinsurance's details. not even on browser.
    pass


class LCLBrowser(LoginBrowser, StatesMixin):
    BASEURL = 'https://monespace.lcl.fr'

    keypad = URL(r'/api/login/keypad', KeypadPage)
    login = URL(r'/api/login', LoginPage)
    login_contract = URL(r'/api/login/contract')
    user_contract = URL(r'/api/user/contract')
    authorized_operations = URL(r'/api/user/authorized_operations\?contract_id=(?P<contracts_id>.*)')
    pre_access = URL(r'/api/user/messaging/pre-access')
    launch_redirection = URL(
        r'https://(?P<website>.+).secure.lcl.fr/outil/UAUT/warbel-context-provider',
        LaunchRedirectionPage
    )
    redirection = URL(r'https://(?P<website>.+).secure.lcl.fr/outil/UAUT/Contract/redirection', RedirectionPage)

    pre_home = URL(r'https://(?P<website>.+).secure.lcl.fr/outil/UWER/Accueil/majicER', PreHomePage)
    home = URL(r'https://(?P<website>.+).secure.lcl.fr/outil/UWHO/Accueil/', HomePage)

    redirect_monespace_home = URL(
        r'https://(?P<website>.+).secure.lcl.fr/outil/UAUT/acces_refonte\?xtatc=INT-937',
        RedirectMonEspaceHome
    )
    monespace_home = URL(r'/connexion/legacy', MonEspaceHome)
    aggregation = URL(r'/api/user/accounts/aggregation\?contract_id=(?P<contracts_id>.*)', AggregationPage)

    accounts = URL(
        r'/api/user/accounts\?type=current&contract_id=(?P<contracts_id>.*)&is_eligible_for_identity=false&include_aggregate_account=false',
        AccountsPage
    )
    savings = URL(
        r'/api/user/accounts\?type=saving&contract_id=(?P<contracts_id>.*)&is_eligible_for_identity=false&include_aggregate_account=false',
        AccountsPage
    )
    term_accounts = URL(r'/api/user/accounts/term_accounts\?contract_id=(?P<contracts_id>.*)', TermAccountsPage)
    cards = URL(
        r'/api/user/cards/deferred\?contract_id=(?P<contracts_id>.*)&include_aggregation=false',
        CardsPage
    )
    cards_synthesis = URL(r'/api/user/cards/synthesis\?contract_id=(?P<contracts_id>.*)', CardSynthesisPage)
    card_details = URL(r'/api/user/cards/(?P<card_id>.*)/detail', CardDetailsPage)
    life_insurances = URL(
        r'/api/user/accounts/life_insurances\?contract_id=(?P<contracts_id>.*)&include_aggregate_account=false',
        LifeInsurancesPage
    )
    loans = URL(
        r'/api/user/loans\?contract_id=(?P<contracts_id>.*)&include_aggregate_loan=false',
        LoansPage
    )
    loan_details = URL(
        r'/api/user/loans/(?P<loan_id>.*)\?source_code=(?P<source_code>.*)&product_code=(?P<product_code>.*)&branch=(?P<branch>.*)&account=(?P<account>.*)&is_aggregate_loan=false&contract_id=(?P<contracts_id>.*)',
        LoanDetailsPage
    )
    revolvings = URL(r'api/user/loans/revolving\?contract_id=(?P<contracts_id>.*)&include_aggregate_loan=false')

    transactions = URL(
        r'/api/user/accounts/(?P<account_id>.*)/transactions\?contract_id=(?P<contracts_id>.*)&range=(?P<begin>.+)-(?P<end>.+)',
        TransactionsPage
    )
    cards_transactions = URL(
        r'/api/user/cards/(?P<card_id>.*)/transactions\?contract_id=(?P<contracts_id>.*)',
        CardTransactionsPage
    )
    sepa_mandate = URL(
        r'/api/user/accounts/sepa/debits\?contract_id=(?P<contracts_id>.*)&account_id=(?P<account_id>.*)&number_of_days=14&range=(?P<begin>.+)-(?P<end>.+)',
        SEPAMandatePage
    )

    routage = URL(r'https://(?P<website>.+).secure.lcl.fr/outil/UWVI/Routage', RoutagePage)
    get_contract = URL(r'https://(?P<website>.+).secure.lcl.fr/outil/UAUT/Contract/getContract', GetContractPage)
    av_transactions = URL(r'https://assurance-vie-et-prevoyance.secure.lcl.fr/rest/assurance/historique', AVHistoryPage)
    av_investments = URL(
        r'https://assurance-vie-et-prevoyance.secure.lcl.fr/rest/detailEpargne/contrat',
        AVInvestmentsPage
    )

    # Documents
    documents = URL(r'/api/user/documents/accounts_statements', DocumentsPage)
    download_document = URL(r'/api/user/documents/download\?downloadToken=(?P<token>.*)')
    bourse_home = URL(r'https://particuliers.secure.lcl.fr/outil/UWMI/Accueil/accueil', BourseHomePage)
    bourse = URL(
        r'https://bourse.secure.lcl.fr/netfinca-titres/servlet/com.netfinca.frontcr.synthesis.HomeSynthesis',
        r'https://bourse.secure.lcl.fr/netfinca-titres/servlet/com.netfinca.frontcr.account.*',
        r'https://(?P<website>.+).secure.lcl.fr/outil/UWBO.*',
        BoursePage
    )
    no_perm = URL(r'/outil/UAUT/SansDroit/affichePageSansDroit.*', NoPermissionPage)
    disc = URL(
        r'https://bourse.secure.lcl.fr/netfinca-titres/servlet/com.netfinca.frontcr.login.ContextTransferDisconnect',
        r'https://assurance-vie-et-prevoyance.secure.lcl.fr/filiale/entreeBam\?.*\btypeaction=reroutage_retour\b',
        r'https://assurance-vie-et-prevoyance.secure.lcl.fr/filiale/ServletReroutageCookie',
        r'https://(?P<website>.+).secure.lcl.fr/outil/UAUT/RetourPartenaire/retourCar',
        DiscPage
    )

    __states__ = ('session_id', 'contract_id', 'encoded_contract_id', 'user_name')

    def __init__(self, config, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.session_id = ''.join(random.choices(string.digits, k=29))
        self.website = self.update_website(config['website'].get())
        if not re.match(r'^\d{10}$', self.username):
            raise BrowserIncorrectPassword('Login should be composed of 10 numbers', bad_fields=['login'])
        if not re.match(r'^\d{6}$', self.password):
            raise BrowserIncorrectPassword('Password should be composed of 6 numbers', bad_fields=['password'])

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
                if code in ('BAD_CREDENTIALS_AND_TEMPORARY_BLOCKING', 'CREDENTIALS_BLOCKED', 'ACCESS_BLOCKED'):
                    raise BrowserUserBanned()
                raise AssertionError(f'Unhandled error code during login. code:{code}, message:{message}')
            raise AssertionError('Unhandled error during login')

        (
            self.token, self.refresh_token, self.expire_date, self.encrypted_expire_date, self.redirect_user_id,
        ) = self.page.get_authentication_data()
        self.session.headers['X-Authorization'] = f'Bearer {self.token}'

        # MFA check
        self.mfa_type, self.device_name = self.page.get_mfa_details()
        if self.mfa_type:
            raise ActionNeeded(
                locale="fr-FR", message="Veuillez réaliser l'authentification forte depuis votre navigateur.",
                action_type=ActionType.PERFORM_MFA,
            )

        self.contract_id = self.page.get_contract_id(website=self.website)
        self.encoded_contract_id = self.encode_64(self.contract_id)[:-2]
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

        try:
            self.authorized_operations.go(contracts_id=self.encoded_contract_id)
            self.pre_access.go()
        except ClientError:
            # encountred on a connection where we get redirected to the legacy website (in the browser)
            # unable to reproduce since then.
            self.logger.info('Redirect to legacy website required.')

            self.go_legacy_website()

            self.redirect_monespace_home.go(website=self.website)
            assert self.monespace_home.is_here(), 'expected to be in monespace_home'

            self.aggregation.go(contracts_id=self.encoded_contract_id)

    @need_login
    def iter_accounts(self):
        # website: `Espace Bourse`
        bourse_accounts = []
        if self.go_bourse_website() and self.connexion_bourse():
            for account in self.page.get_list():
                bourse_accounts.append(account)
                yield account
            self.deconnexion_bourse()

        checking_accounts = []
        self.accounts.go(contracts_id=self.encoded_contract_id)
        for account in self.page.iter_accounts(user_name=self.user_name):
            # Liquidity accounts listed as checking
            account.parent = find_object(bourse_accounts, number=account.number)
            if account.parent:
                account._overwritten_type = account.type
                account.type = account.parent.type

            checking_accounts.append(account)
            yield account

        self.savings.go(contracts_id=self.encoded_contract_id)
        # yield from self.page.iter_accounts(user_name=self.user_name)
        for account in self.page.iter_accounts(user_name=self.user_name):
            # Liquidity accounts listed as savings
            account.parent = find_object(bourse_accounts, number=account.number)
            if account.parent:
                account._overwritten_type = account.type
                account.type = account.parent.type
            yield account

        self.term_accounts.go(contracts_id=self.encoded_contract_id)
        yield from self.page.iter_accounts(user_name=self.user_name)

        self.cards.go(contracts_id=self.encoded_contract_id)
        for card in self.page.iter_cards(user_name=self.user_name):
            card.parent = find_object(checking_accounts, _internal_id=card._parent_internal_id)

            # if card not mentionned in synthesis page, then it should be skipped
            self.cards_synthesis.go(contracts_id=self.encoded_contract_id)
            if self.page.is_card_available(card._internal_id):
                self.card_details.go(card_id=self.encode_64(card._internal_id)[:-1])
                self.page.fill_card(obj=card)

            yield card

        try:
            self.life_insurances.go(contracts_id=self.encoded_contract_id)
        except ClientError:
            # does not have life insurance
            pass
        else:
            yield from self.page.iter_accounts(user_name=self.user_name)

        self.loans.go(contracts_id=self.encoded_contract_id)
        for loan in self.page.iter_loans():
            loan.parent = find_object(checking_accounts, id=loan._parent_id)

            try:
                # fill the loan's details
                self.loan_details.go(
                    loan_id=loan.id,
                    source_code=loan._source_code,
                    product_code=loan._product_code,
                    branch=loan._branch,
                    account=loan._account,
                    contracts_id=self.encoded_contract_id,
                )
            except (ClientError, ServerError):
                # there's a real website problem
                self.logger.warning(f"Could not access loan details. Skipping. Loan's amount: {loan.total_amount}")
            else:
                self.logger.info('Successfully reached loan details.')
                self.page.fill_loan(obj=loan)
                # sometimes the `_parent_id` is not enough to find the parent
                if not loan.parent:
                    if empty(loan._iban):
                        self.logger.warning("Can't find loan's parent. No iban.")
                    else:
                        loan.parent = find_object(checking_accounts, iban=loan._iban)
                yield loan

    @need_login
    def iter_history(self, account):
        ALLOWED_TYPES = (
            Account.TYPE_CHECKING, Account.TYPE_SAVINGS, Account.TYPE_PEA, Account.TYPE_CARD,
            Account.TYPE_DEPOSIT, Account.TYPE_LIFE_INSURANCE, Account.TYPE_MARKET,
        )
        if (
            account.type not in ALLOWED_TYPES
            and not (
                hasattr(account, '_overwritten_type') and account._overwritten_type in ALLOWED_TYPES
            )
        ):
            return

        if empty(account._internal_id) and empty(account._market_link):
            # no `_internal_id` => has no history (observed case: 'OPTILION STRATEGIQUE ECHEANCE' from TermAccountsPage)
            # except if `_market_link` => account comes from boursepage
            return

        if account._market_link:
            self.go_bourse_website()
            self.connexion_bourse()
            self.location(
                account._link_id, params={
                    'nump': account._market_id,
                }
            )
            self.page.get_fullhistory()
            yield from self.page.iter_history()
            self.deconnexion_bourse()
            return

        if account.type == Account.TYPE_CARD:
            self.cards_transactions.go(card_id=account._id, contracts_id=self.encoded_contract_id)
            yield from self.page.iter_transactions()
            return

        if account.type == Account.TYPE_LIFE_INSURANCE:
            try:
                self.go_life_insurance_website(account)
            except LifeInsuranceNotAvailable:
                return

            self.av_transactions.go()
            yield from self.page.iter_history()
            return

        begin = 0
        end = 99
        stop_condition = False
        counter = 0
        while not stop_condition and counter < 50:
            self.transactions.go(
                account_id=account._internal_id,
                begin=begin,
                end=end,
                contracts_id=self.encoded_contract_id,
            )
            yield from self.page.iter_transactions()
            begin += 100
            end += 100
            stop_condition = self.page.update_stop_condition()
            counter += 1

    @need_login
    def iter_coming(self, account):
        if account.type != Account.TYPE_DEPOSIT:
            return

        # SEPA Mandate
        begin = 0
        end = 99
        stop_condition = False
        counter = 0
        while not stop_condition and counter < 50:
            self.sepa_mandate.go(
                account_id=account._internal_id,
                begin=begin,
                end=end,
                contracts_id=self.encoded_contract_id,
            )
            yield from self.page.iter_transactions()
            begin += 100
            end += 100
            stop_condition = self.page.update_stop_condition()
            counter += 1

    def iter_investment(self, account):
        ALLOWED_TYPES = (Account.TYPE_LIFE_INSURANCE, Account.TYPE_MARKET, Account.TYPE_PEA)
        ALLOWED_OVERWRITTEN_TYPES = (Account.TYPE_CHECKING, Account.TYPE_SAVINGS, Account.TYPE_DEPOSIT)

        if (
            account.type not in ALLOWED_TYPES
            and not (
                hasattr(account, '_overwritten_type') and account._overwritten_type in ALLOWED_TYPES
            )
        ):
            return

        # ACCOUNT IN BOURSE PAGE
        if account._market_link:
            self.go_bourse_website()
            self.connexion_bourse()
            self.location(account._market_link)
            yield from self.page.iter_investment(account_currency=account.currency)
            self.deconnexion_bourse()
            return

        # LIQUIDITY ACCOUNT FOR A MARKET/PEA ACCOUNT IN BOURSE PAGE
        if hasattr(account, '_overwritten_type') and account._overwritten_type in ALLOWED_OVERWRITTEN_TYPES:
            yield create_french_liquidity(account.balance)
            return

        if account.type == Account.TYPE_LIFE_INSURANCE:
            try:
                self.go_life_insurance_website(account)
            except LifeInsuranceNotAvailable:
                return

            self.av_investments.go()
            yield from self.page.iter_investment()
            return

        self.logger.warning('Unhandled case.')

    def go_legacy_website(self):
        del self.session.headers['X-Authorization']
        self.session.headers.update({
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Referer': 'https://monespace.lcl.fr/',
        })
        self.launch_redirection.go(
            website=self.website,
            data={
                'token': self.token,
                'rt': self.refresh_token,
                'exp': self.encrypted_expire_date,
                'ib': self.redirect_user_id,
            },
            headers={
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Referer': 'https://monespace.lcl.fr/',
            }
        )

        if self.launch_redirection.is_here():
            message = self.page.get_message()
            if "Pour accéder à l'ensemble des fonctionnalités" in message:
                # the user needs to use new credentials the bank sent them.
                # the current credentials are temporary and give limited access.
                raise ActionNeeded(message)
            raise AssertionError(f'Wrong redirection. message: {message}.')

        assert self.redirection.is_here(), 'expected to be in redirection'
        self.page.go_pre_home()

        assert self.pre_home.is_here(), 'expected to be in pre_home'
        self.page.go_home()

        assert self.home.is_here(), 'expected to be in home'

    @retry(LifeInsuranceUnreachable)
    def go_life_insurance_website(self, account):
        try:
            self.launch_redirection.go(
                website=self.website,
                data={
                    'token': self.token,
                    'rt': self.refresh_token,
                    'exp': self.encrypted_expire_date,
                    'ib': self.redirect_user_id,
                    'from': '/outil/UWVI/Routage',
                    'monEspaceRouteBack': self.encode_64('/synthese/epargne'),
                    'redirectTo': account._partner_label,  # ex: 'PREDICA'
                    'isFromNewApp': 'true',
                    'ORIGINE_URL': 'SAV',
                    'NUM_CONTRAT': account.id,
                    'PRODUCTEUR': account._partner_code,  # ex: '02'
                },
            )
        except ServerError as error:
            if error.response.status_code == 500:
                raise LifeInsuranceUnreachable()
            raise

        if self.get_contract.is_here():
            raise LifeInsuranceNotAvailable()

        if not self.routage.is_here():
            raise AssertionError('Unexpected redirection')

        self.page.send_form()

    @need_login
    def go_bourse_website(self):
        self.launch_redirection.go(
            website=self.website,
            data={
                'token': self.token,
                'rt': self.refresh_token,
                'exp': self.encrypted_expire_date,
                'ib': self.redirect_user_id,
                'from': '/outil/UWMI/Bourse',
                'monEspaceRouteBack': self.encode_64('/synthese/epargne'),
                'redirectTo': 'BOURSE',
                'canal': 'WEB',
                'isFromNewApp': 'true',
            },
        )
        if self.bourse_home.is_here():
            return True
        return False

    @need_login
    def connexion_bourse(self):
        contract_type = CONTRACT_TYPES[self.website]
        self.location(
            f'https://{self.website}.secure.lcl.fr/outil/UWBO/AccesBourse/temporisationCar?codeTicker=TICKERBOURSE{contract_type}',
            data=''
        )
        if self.no_perm.is_here():
            return False
        next_page = self.page.get_next()
        if next_page:
            # go on a intermediate page to get a session cookie (jsessionid)
            self.location(next_page)
            # go to bourse page
            self.bourse.stay_or_go()
            return True

    def deconnexion_bourse(self):
        self.disc.stay_or_go()

    @staticmethod
    def encode_64(contract_id):
        return b64encode(contract_id.encode('ascii')).decode('ascii')

    @staticmethod
    def update_website(website):
        if website == 'pro':
            return 'professionnels'

        # default to 'particuliers'
        return 'particuliers'

    @need_login
    def iter_subscriptions(self):
        self.accounts.go(contracts_id=self.encoded_contract_id)
        return self.page.iter_subscriptions()

    @need_login
    def iter_documents(self, subscription):
        today = date.today()
        start = today - relativedelta(years=10)
        str_start = start.strftime('%Y-%m-%d')
        str_end = today.strftime('%Y-%m-%d')
        params = {
            'initial_date': str_start,
            'final_date': str_end,
            'market_code': '01,02,21',
        }
        self.documents.go(params=params)
        return self.page.iter_documents(subid=subscription.id)
