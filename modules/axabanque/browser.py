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

# flake8: compatible

import re
import random
from datetime import date
from base64 import b64encode
from hashlib import sha256
from urllib.parse import urljoin, urlparse

from dateutil.relativedelta import relativedelta

from woob.browser import LoginBrowser, URL, need_login
from woob.browser.exceptions import BrowserUnavailable, ClientError, ServerError
from woob.browser.filters.standard import QueryValue
from woob.browser.switch import SiteSwitch
from woob.capabilities.bank import Account
from woob.exceptions import (
    BrowserPasswordExpired, BrowserIncorrectPassword, ActionNeeded, ActionType,
)
from woob.tools.capabilities.bank.transactions import sorted_transactions
from woob.tools.decorators import retry
from woob_modules.allianzbanque.browser import AllianzbanqueBrowser

from .pages.bank import AccountsPage
from .pages.login import (
    LoginPage, ChangepasswordPage, PredisconnectedPage, DeniedPage,
    AccountSpaceLogin, ErrorPage, AuthorizePage, InfiniteLoopPage, LoginEndPage,
)
from .pages.wealth import (
    AccountsPage as WealthAccountsPage, AccountDetailsPage, InvestmentPage,
    InvestmentMonAxaPage, HistoryPage, HistoryInvestmentsPage, ProfilePage,
    PerformanceMonAxaPage, InvestmentJsonPage, AccessBoursePage, FormHistoryPage,
    BourseAccountsPage, WealthHistoryPage, NewInvestmentPage, InsuranceAccountsBouncerPage,
    HomePage, ClearSessionPage, InvestmentErrorPage, OutremerProfilePage,
)
from .pages.document import SubscriptionsPage, DocumentsPage

WEALTH_ACCOUNTS = (
    Account.TYPE_LIFE_INSURANCE, Account.TYPE_MADELIN, Account.TYPE_PER, Account.TYPE_PERP,
)


class AXAOldLoginBrowser(LoginBrowser):
    # Login
    login = URL(r'https://connect.axa.fr/api/identity/auth', LoginPage)
    password = URL(r'https://connect.axa.fr/#/changebankpassword', ChangepasswordPage)
    predisconnected = URL(
        r'https://www.axa.fr/axa-predisconnect.html',
        r'https://www.axa.fr/axa-postmaw-predisconnect.html',
        PredisconnectedPage
    )
    authorize = URL(r'https://connect.axa.fr/connect/authorize', AuthorizePage)
    denied = URL(r'https://connect.axa.fr/Account/AccessDenied', DeniedPage)
    account_space_login = URL(r'https://connect.axa.fr/api/accountspace', AccountSpaceLogin)
    errors = URL(
        r'https://espaceclient.axa.fr/content/ecc-public/accueil-axa-connect/_jcr_content/par/text.html',
        r'https://espaceclient.axa.fr/content/ecc-public/errors/500.html',
        ErrorPage
    )
    login_end = URL(r'https://espaceclient.axa.fr/$', LoginEndPage)
    infinite_redirect = URL(
        r'http[s]?://www.axabanque.fr/webapp/axabanque/jsp(/erreur)?/[\d\.:]+/webapp/axabanque/jsp/erreur/erreurBanque',
        # ex: 'http://www.axabanque.fr/webapp/axabanque/jsp/172.25.100.12:80/webapp/axabanque/jsp/erreur/erreurBanque.faces'
        InfiniteLoopPage
    )

    def __init__(self, config, username, password, *args, **kwargs):
        super(AXAOldLoginBrowser, self).__init__(username, password, *args, **kwargs)

    def do_login(self):
        # Due to the website change, login changed too.
        # This is for avoiding to log-in with the wrong login
        if self.username.isdigit() and len(self.username) > 7:
            raise BrowserPasswordExpired()

        self.account_space_login.go()
        password_message = self.page.get_password_information_message()
        if 'votre code confidentiel doit être modifié' in password_message and self.password.isdigit():
            raise BrowserPasswordExpired(
                locale='fr-FR',
                message=password_message
            )

        error_message = self.page.get_error_message()
        if error_message:
            is_website_unavailable = re.search(
                "Veuillez nous excuser pour la gêne occasionnée"
                + "|votre espace client est temporairement indisponible",
                error_message
            )

            if is_website_unavailable:
                raise BrowserUnavailable(error_message)

        if self.page.get_error_link():
            # Go on information page to get possible error message
            self.location(self.page.get_error_link())

        login_data = {
            'email': self.username,
            'password': self.password,
            'rememberIdenfiant': False,
        }

        self.location('https://connect.axa.fr')
        try:
            self.login.go(
                json=login_data,
                headers={'X-XSRF-TOKEN': self.session.cookies['XSRF-TOKEN']}
            )
        except ClientError as err:
            response = err.response
            if response.status_code == 400 and 'INVALID_CREDENTIAL' in response.text:
                raise BrowserIncorrectPassword()
            raise

        if self.page.check_error():
            raise BrowserIncorrectPassword()

        if self.page.password_expired():
            raise BrowserPasswordExpired()

        url = self.page.get_url()
        if 'bank-otp' in url:
            # The SCA is Cross-Browser so the user can do the SMS validation on the website
            # and then try to synchronize the connection again.
            raise ActionNeeded(
                locale="fr-FR", message="Vous devez réaliser la double authentification sur le portail internet",
                action_type=ActionType.PERFORM_MFA,
            )

        # home page to finish login
        self.location('https://espaceclient.axa.fr/', allow_redirects=False)
        for _ in range(13):
            # When trying to reach home we are normally redirected a few times.
            # But very rarely we are redirected 13 times before entering
            # an infinite redirection loop between 'infinite_redirect'
            # url to another. Need to try later.
            location = self.response.headers.get('location')
            if not location:
                break
            self.location(location)
            if self.infinite_redirect.is_here():
                raise BrowserUnavailable()


class AXANewLoginBrowser(AllianzbanqueBrowser):
    BASEURL = 'https://api-banque.axa.fr'
    redirect_uri = 'https://banque.axa.fr/auth/checkuser'
    error_uri = 'https://banque.axa.fr/auth/errorauthn'
    arkea = 'AB'  # Needed for the X-ARKEA-EFS header
    arkea_si = '0AB'
    arkea_client_id = 'O7v09LGq4zJsi5BWfuAGFK6KGLoX3QVh'  # Hardcoded in app.js, line 33808
    original_site = 'https://banque.axa.fr'

    def code_challenge(self):
        """Generate a code challenge needed to go through the authorize end point
        and get a session id.

        The process to generate this code_challenge:

        - Generate a 128 length string from which characters are randomly choosen
        among the base string.
        - b64encode this string
        - Replace '=', '+', '/' respectively with these '', '-' and '_'.

        Found in domi-auth-fat.js at line 39501"""

        base = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~'
        code_challenge = b64encode(
            ''.join(random.choices(base, k=128)).encode('utf-8')
        ).decode('utf-8').replace('=', '').replace('+', '-').replace('/', '_')
        return code_challenge

    def auth_state(self):
        """Generate a state needed to go through the authorize end point
        and get a session id.
        Found in domi-auth-fat.js at line 39518"""

        base = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
        state = 'auth_' + ''.join(random.choices(base, k=25))

        return state

    def code_verifier(self, code_challenge):
        """Generate a code verifier that will have to match the sha256 of the code_challenge
        on the server side.
        Found in domi-auth-fat.js at line 39509"""

        digest = sha256(code_challenge.encode('utf-8')).digest()
        code_verifier = b64encode(digest)

        return code_verifier.decode()

    def get_pkce_codes(self):
        """Override parent because Axa did things well
        and did not use verifier for code_challenge and vice versa."""
        code_challenge = self.code_challenge()
        return self.code_verifier(code_challenge), code_challenge

    def build_authorization_uri_params(self):
        params = super(AXANewLoginBrowser, self).build_authorization_uri_params()
        params['state'] = self.auth_state()
        return params

    def setup_space_after_login(self):
        """Override from parent because AXABanque has no Pro/Part space."""
        pass


class AXABanqueBrowser(AXANewLoginBrowser):
    STATE_DURATION = 10

    home = URL(r'https://espaceclient-connect.axa.fr/', HomePage)

    insurance_accounts_bouncer = URL(
        r'/oidc/init-sso-axf',
        InsuranceAccountsBouncerPage,
    )
    insurances = URL(
        r'https://(?P<url_domain>.*).axa.fr/content/(?P<url_path>.*)/accueil.content-inner.html',
        WealthAccountsPage
    )
    clear_session = URL(r'https://connect.axa.fr/identity/clear-session', ClearSessionPage)
    authorize = URL(r'/oauth/authorize', AuthorizePage)
    accounts = URL(r'/distri-account-api/api/v1/persons/me/accounts', AccountsPage)
    transactions_comings = URL(
        r'/distri-account-api/api/v1/persons/me/accounts/(?P<account_id>[A-Z0-9]{10})/upcoming-transactions',
        AccountsPage
    )

    subscriptions = URL(r'/distri-account-api/api/v1/customers/me/accounts', SubscriptionsPage)
    documents = URL(r'/documentapi/api/v2/vaults/(?P<contract_id>.*)/documents$', DocumentsPage)
    document_pdf = URL(r'/documentapi/api/v2/vaults/(?P<contract_id>.*)/documents/(?P<document_id>.*)/file')

    __states__ = (
        'axa_assurance_base_url', 'axa_assurance_url_path', 'is_coming_from_axa_bank',
    )

    def locate_browser(self, state):
        # access_token lasts 180 seconds according to the JSON in which
        # we get it but when browsing the website, it is in fact valid
        # for about 10 minutes. Anyway, this is too short to store it so
        # to avoid 401 on some URLs, just skip locate_browser and relog.
        pass

    def __init__(self, *args, **kwargs):
        super(AXABanqueBrowser, self).__init__(*args, **kwargs)
        self.axa_assurance_base_url = None
        self.axa_assurance_url_path = None
        self.is_coming_from_axa_bank = None

    @need_login
    def iter_accounts(self):
        self.accounts.go(params={'types': 'CHECKING,SAVING'})
        for account in self.page.iter_accounts():
            self.balances.go(account_id=account.id)
            self.page.fill_balance(account)
            date_to = (date.today() + relativedelta(months=1)).strftime('%Y-%m-%dT00:00:00.000Z')
            go_balances_comings = retry(ServerError, tries=5)(self.balances_comings.go)
            go_balances_comings(account_id=account.id, params={'dateTo': date_to})
            self.page.fill_coming(account)
            yield account

        if self.go_to_insurance_accounts():
            for acc in self.page.iter_accounts():
                yield acc

    def go_to_insurance_accounts(self):
        self.insurance_accounts_bouncer.go()

        # First time we go to insurance_accounts_bouncer, we're always correctly
        # redirected to either outremer or classic space. If we ever have to load
        # this URL again during the same session, redirection process will stop
        # on clear_session URL that contains the needed redirection in its parameters
        # but won't call it automatically. Calling it manually makes the redirection
        # process be the same as when we first load insurance_accounts_bouncer.
        if self.clear_session.is_here():
            return_url = QueryValue(None, 'returnUrl').filter(self.url)
            self.location(return_url)

        # In case the user has only a bank space, but no insurance one.
        if self.home.is_here():
            return False

        self.axa_assurance_base_url = self.url
        if urlparse(self.url).netloc == 'outremer.axa.fr':
            # All attributes here will be needed when switching browser
            self.axa_assurance_url_path = 'outremer-espace-client'
            self.insurances.go(url_domain='outremer', url_path=self.axa_assurance_url_path)
        else:
            self.axa_assurance_url_path = 'espace-client'
            self.insurances.go(url_domain='espaceclient', url_path=self.axa_assurance_url_path)

        # If we're here, then we are going to switch to insurance browser later and this information
        # will be needed to distinguish AXABanqueBrowser accounts that also have insurances from
        # AXAAssuranceBrowser that only have insurances and for which the login is different
        self.is_coming_from_axa_bank = True

        return True

    @need_login
    def iter_history(self, account):
        # History for bank account is well managed by parents
        if account.type in (Account.TYPE_CHECKING, Account.TYPE_SAVINGS):
            return super(AXABanqueBrowser, self).iter_history(account)
        # On the other hand for wealth products, there's a dedicated space for them
        # Which has nothing to do with parents modules
        elif account.type in (Account.TYPE_MARKET, Account.TYPE_PEA):
            raise SiteSwitch('bourse')
        elif account.type in WEALTH_ACCOUNTS:
            raise SiteSwitch('insurance')
        else:
            return []

    @need_login
    def iter_investment(self, account):
        if account.type == Account.TYPE_MARKET:
            raise SiteSwitch('bourse')
        elif account.type in WEALTH_ACCOUNTS:
            raise SiteSwitch('insurance')
        return []

    @need_login
    def get_subscription_list(self):
        params = {
            'types': 'CHECKING',
            'roles': 'TIT,COT',
        }
        self.subscriptions.go(params=params)
        return self.page.iter_subscriptions()

    @need_login
    def iter_documents(self, subscription):
        self.documents.go(contract_id=subscription._contract_id)
        return self.page.iter_documents(subid=subscription.id, contract_id=subscription._contract_id)

    @need_login
    def download_document(self, document):
        params = {'flattenDoc': False}
        return self.open(document.url, params=params).content


class AXABourseBrowser(AXABanqueBrowser):
    BASEURL = 'https://bourse.axa.fr/'

    request_access = URL(r'https://api-banque.axa.fr/sso-domifront/cypher\?service=bourse', AccessBoursePage)
    bourse = URL(r'/receiver')

    accounts = URL(r'/secure_main/accounts_list.html\?navId=SYN', BourseAccountsPage)
    history = URL(r'/secure_account/selectedAccountMovements.html', WealthHistoryPage)
    form_history = URL(r'/secure_ajax/accountMovementsResult.html', FormHistoryPage)
    investments = URL(r'/secure_account/selectedAccountDetail.html', NewInvestmentPage)

    def do_login(self):
        """The way we logging in the bourse space is a little bit special.
        We access it from the AxaBanque user space and by requesting access. Thus
        we obtain a token that is passed in parameter of the receiver endpoint."""
        self.request_access.go()
        cypher = self.page.get_cypher()

        self.bourse.go(params={'cypher': cypher})

    @need_login
    def iter_history(self, account):
        if account.type in (Account.TYPE_CHECKING, Account.TYPE_SAVINGS):
            raise SiteSwitch('main')
        elif account.type in WEALTH_ACCOUNTS:
            raise SiteSwitch('insurance')

        """History of operations is quite a mess.
            We need to deal with a double pagination:

            First, we have to select a range of time through the history form.
            This is our first pagination, we iterate over years, over and over, until there's no more transactions.

            Second, for each range of year, AxaBanque pagine transactions ten by ten
            This is our second pagination. We iterate over each pack of ten transactions
            until we've reached the last page.
        """
        # First, if the wealth account is a market/PEA one
        # We need to collect related investments
        # So we can match transactions with them
        investments = self.iter_investment(account)
        # Mapping invest with their ISIN code so we won't
        # have to double loop over transactions and then investments
        # to do the match
        investments = {invest.code: [invest] for invest in investments}
        self.accounts.stay_or_go()
        self.history.go(
            params={'cipher': self.page.get_cipher(account.number)},
        )

        end_date = date.today()
        begin_date = end_date - relativedelta(years=1)
        transactions = []

        while True:
            self.form_history.go(
                data={
                    'siteLanguage': 'fr',
                    'beginDate': begin_date.strftime('%d/%m/%Y'),
                    'endDate': end_date.strftime('%d/%m/%Y'),
                },
            )
            if not self.page.has_more_transactions():
                break
            end_date -= relativedelta(years=1)
            begin_date -= relativedelta(years=1)
            transactions.extend(self.page.iter_history(investments=investments))

        return transactions

    @need_login
    def iter_investment(self, account):
        if account.type in (Account.TYPE_CHECKING, Account.TYPE_SAVINGS):
            raise SiteSwitch('main')
        elif account.type in WEALTH_ACCOUNTS:
            raise SiteSwitch('insurance')

        if account.balance > 0:
            self.accounts.stay_or_go()
            self.investments.go(
                params={'cipher': self.page.get_cipher(account.number)},
            )
            return self.page.iter_investments()
        return []


class AXAAssuranceBrowser(AXAOldLoginBrowser):
    BASEURL = 'https://espaceclient.axa.fr'  # Default BASEURL for AXAAssuranceBrowser accounts only

    accounts = URL(
        r'/content/(?P<url_path>.*)/accueil.content-inner.html',
        WealthAccountsPage,
    )
    history = URL(
        r'/accueil/savings/savings/contract/_jcr_content.eccGetSavingsOperations.json',
        HistoryPage,
    )
    history_investments = URL(
        r'/accueil/savings/savings/contract/_jcr_content.eccGetSavingOperationDetail.json',
        HistoryInvestmentsPage,
    )
    details = URL(
        r'.*accueil/savings/(\w+)/contract',
        r'/#',
        AccountDetailsPage,
    )
    investment_error = URL(
        r'/public/errors/500.html',
        InvestmentErrorPage,
    )
    investment = URL(
        r'/content/ecc-popin-cards/savings/[^/]+/repartition',
        r'/popin-cards/savings/[^/]+/repartition/.*',
        InvestmentPage,
    )
    investment_json = URL(
        r'/content/(?P<url_path>.*)/accueil/_jcr_content.savingsDistribution.json',
        InvestmentJsonPage,
    )
    investment_monaxa = URL(r'https://monaxaweb-gp.axa.fr/MonAxa/Contrat/', InvestmentMonAxaPage)
    performance_monaxa = URL(r'https://monaxaweb-gp.axa.fr/MonAxa/ContratPerformance/', PerformanceMonAxaPage)

    profile = URL(
        r'/content/ecc-popin-cards/transverse/userprofile.content-inner.html\?_=\d+',
        ProfilePage,
    )
    outremer_profile = URL(
        r'/content/outremer-espace-client/popin-cards/transverse/userprofile.content-inner.html\?_=\d+',
        OutremerProfilePage,
    )

    def __init__(self, *args, **kwargs):
        super(AXAAssuranceBrowser, self).__init__(*args, **kwargs)
        self.axa_assurance_url_path = 'espace-client'  # Default path for URLs for AXAAssuranceBrowser accounts only
        self.is_coming_from_axa_bank = None  # Default for AXAassuranceBrowser accounts only

    def set_base_url(self):
        # BASEURL can't be defined in the __init__ because SwitchingBrowser set the values from
        # the __states__ as attributes for the second browser only after that second browser has been instanciated.
        # BASEURL can't be set as a property too because SwitchingBrowser will directly call the method it has
        # been given in the first browser, e.g. if we came from browser 1 with iter_investment, then
        # we have no choice but to call set_base_url() at the beginning of the method in browser 2.
        if self.is_coming_from_axa_bank:
            self.BASEURL = self.axa_assurance_base_url

    def go_wealth_pages(self, account):
        # Sometimes, a random page about an error 500 can be returned
        # with a status_code 200 and website itself says it might work
        # after reloading the page
        location = retry(ClientError)(self.location)
        location(urljoin(self.BASEURL, account.url))
        if self.investment_error.is_here():  # If retrying failed
            raise BrowserUnavailable()
        self.location(self.page.get_account_url(account.url))

    @need_login
    def iter_accounts(self):
        self.accounts.go(url_path=self.axa_assurance_url_path)
        return self.page.iter_accounts()

    # Logged property is needed when switching from the main browser
    # to the insurance browser.
    @property
    def logged(self):
        return bool(self.session.headers.get('Authorization'))

    @need_login
    def iter_investment_espaceclient(self, account):
        invests = []
        portfolio_page = self.page
        detailed_view = self.page.detailed_view()
        if detailed_view:
            self.location(detailed_view)
            invests.extend(self.page.iter_investment(currency=account.currency))
        for inv in portfolio_page.iter_investment(currency=account.currency):
            i = [i2 for i2 in invests if
                 (i2.valuation == inv.valuation and i2.label == inv.label)]
            assert len(i) in (0, 1)
            if i:
                i[0].portfolio_share = inv.portfolio_share
            else:
                invests.append(inv)
        return invests

    @need_login
    def iter_investment_monaxa(self, account):
        # Try to fetch a URL to 'monaxaweb-gp.axa.fr'
        invests = list(self.page.iter_investment())

        performance_url = self.page.get_performance_url()
        if performance_url:
            self.location(performance_url)
            for inv in invests:
                self.page.fill_investment(obj=inv)

        # return to espaceclient.axa.fr or outremer.axa.fr
        self.accounts.go(url_path=self.axa_assurance_url_path)
        return invests

    @need_login
    def iter_investment(self, account):
        if account.type in (Account.TYPE_CHECKING, Account.TYPE_SAVINGS):
            return
        elif account.type == Account.TYPE_MARKET:
            raise SiteSwitch('bourse')

        self.set_base_url()

        self.go_wealth_pages(account)
        self.investment_json.go(
            url_path=self.axa_assurance_url_path,
            params={'pid': self.page.get_pid_invest(account.number)}
        )
        if self.investment_json.is_here() and not self.page.is_error():
            return self.page.iter_investments()

        self.go_wealth_pages(account)
        investment_url = self.page.get_investment_url()
        if investment_url:
            self.location(investment_url)
            return self.iter_investment_espaceclient(account)

        iframe_url = self.page.get_iframe_url()
        if iframe_url:
            # Set correct Referer to avoid 302 followed by 406 errors (Not Acceptable)
            base_url = self.BASEURL
            if urlparse(self.page.url).netloc == 'outremer.axa.fr':
                base_url = self.OUTREMER_BASEURL
            headers = {'Referer': f'{base_url}/accueil.html'}
            self.location(iframe_url, headers=headers)
            return self.iter_investment_monaxa(account)

        # No data available for this account.
        self.logger.warning('No investment URL available for account %s, investments cannot be retrieved.', account.id)
        return []

    @need_login
    def iter_history(self, account):
        if account.type in (Account.TYPE_CHECKING, Account.TYPE_SAVINGS):
            raise SiteSwitch('main')
        elif account.type in (Account.TYPE_MARKET, Account.TYPE_PEA):
            raise SiteSwitch('bourse')

        self.set_base_url()

        '''
        Transactions are available 10 by 10 in a JSON.
        To access it, we need the account 'pid' and to increment
        'skip' for each transaction page until the JSON is empty.
        However, transactions are not always in the chronological order.
        '''
        self.go_wealth_pages(account)
        pid = self.page.get_pid()
        skip = 0
        if not pid:
            self.logger.warning('No pid available for account %s, transactions cannot be retrieved.', account.id)
            return

        transactions = []
        self.go_to_transactions(pid, skip)
        # Pagination:
        while self.page.has_operations():
            for tr in self.page.iter_history():
                transactions.append(tr)
            skip += 10
            self.go_to_transactions(pid, skip)

        for tr in sorted_transactions(transactions):
            # Get investments for each transaction
            params = {
                'oid': tr._oid,
                'pid': pid,
            }
            self.history_investments.go(params=params)
            if self.page.has_investments():
                tr.investments = list(self.page.iter_transaction_investments())
            else:
                tr.investments = []
            yield tr

    def go_to_transactions(self, pid, skip):
        params = {
            'pid': pid,
            'skip': skip,
        }
        self.history.go(params=params)

    def iter_coming(self, account):
        raise NotImplementedError()

    def get_subscription_list(self):
        raise NotImplementedError()

    @need_login
    def get_profile(self):
        if 'outremer' in self.BASEURL:
            self.outremer_profile.go()
        else:
            self.profile.go()
        return self.page.get_profile()
