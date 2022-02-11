# -*- coding: utf-8 -*-

# flake8: compatible

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

import re
import random
from datetime import date
from base64 import b64encode
from hashlib import sha256

from dateutil.relativedelta import relativedelta

from woob.browser import LoginBrowser, URL, need_login, AbstractBrowser
from woob.browser.exceptions import BrowserUnavailable
from woob.browser.switch import SiteSwitch
from woob.capabilities.bill import Subscription
from woob.capabilities.bank import Account
from woob.exceptions import BrowserPasswordExpired, BrowserIncorrectPassword, ActionNeeded
from woob.tools.capabilities.bank.transactions import sorted_transactions

from .pages.bank import AccountsPage
from .pages.login import (
    KeyboardPage, LoginPage, ChangepasswordPage, PredisconnectedPage, DeniedPage,
    AccountSpaceLogin, ErrorPage, AuthorizePage, InfiniteLoopPage, LoginEndPage,
)
from .pages.wealth import (
    AccountsPage as WealthAccountsPage, AccountDetailsPage, InvestmentPage,
    InvestmentMonAxaPage, HistoryPage, HistoryInvestmentsPage, ProfilePage,
    PerformanceMonAxaPage, InvestmentJsonPage, AccessBoursePage, FormHistoryPage,
    BourseAccountsPage, WealthHistoryPage, NewInvestmentPage,
)
from .pages.document import DocumentsPage, DownloadPage, DocumentDetailsPage


class AXAOldLoginBrowser(LoginBrowser):
    # Login
    keyboard = URL(r'https://connect.axa.fr/keyboard/password', KeyboardPage)
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
            raise ActionNeeded()

        if self.password.isdigit():
            self.account_space_login.go()

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

            vk_passwd = self.keyboard.go().get_password(self.password)

            login_data = {
                'email': self.username,
                'password': vk_passwd,
                'rememberIdenfiant': False,
            }

            self.location('https://connect.axa.fr')
            self.login.go(data=login_data, headers={'X-XSRF-TOKEN': self.session.cookies['XSRF-TOKEN']})

        if not self.password.isdigit() or self.page.check_error():
            raise BrowserIncorrectPassword()

        if self.page.password_expired():
            raise BrowserPasswordExpired()

        url = self.page.get_url()
        if 'bank-otp' in url:
            # The SCA is Cross-Browser so the user can do the SMS validation on the website
            # and then try to synchronize the connection again.
            raise ActionNeeded('Vous devez réaliser la double authentification sur le portail internet')

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


class AXANewLoginBrowser(AbstractBrowser):
    PARENT = 'allianzbanque'
    PARENT_ATTR = 'package.browser.AllianzbanqueBrowser'

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

        return code_verifier

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

    authorize = URL(r'https://api-banque.axa.fr/oauth/authorize', AuthorizePage)
    accounts = URL(r'/distri-account-api/api/v1/persons/me/accounts', AccountsPage)
    transactions_comings = URL(
        r'/distri-account-api/api/v1/persons/me/accounts/(?P<account_id>[A-Z0-9]{10})/upcoming-transactions',
        AccountsPage
    )

    @need_login
    def iter_accounts(self):
        self.accounts.go(params={'types': 'CHECKING,SAVING'})
        for account in self.page.iter_accounts():
            self.balances.go(account_id=account.id)
            self.page.fill_balance(account)
            date_to = (date.today() + relativedelta(months=1)).strftime('%Y-%m-%dT00:00:00.000Z')
            self.balances_comings.go(account_id=account.id, params={'dateTo': date_to})
            self.page.fill_coming(account)
            yield account

    @need_login
    def iter_history(self, account):
        # History for bank account is well managed by parents
        if account.type in (Account.TYPE_CHECKING, Account.TYPE_SAVINGS):
            return super(AXABanqueBrowser, self).iter_history(account)
        # On the other hand for wealth products, there's a dedicated space for them
        # Which has nothing to do with parents modules
        elif account.type in (Account.TYPE_MARKET, Account.TYPE_PEA):
            raise SiteSwitch('bourse')
        else:
            raise AssertionError('Unhandled account type for iter_history: %s' % account.type)

    @need_login
    def iter_investment(self, account):
        if account.type == Account.TYPE_MARKET:
            raise SiteSwitch('bourse')
        return []

    @need_login
    def get_subscription_list(self):
        raise NotImplementedError()

    @need_login
    def iter_documents(self, subscription):
        raise NotImplementedError()

    @need_login
    def download_document(self, url):
        raise NotImplementedError()


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
        self.accounts.stay_or_go()
        self.investments.go(
            params={'cipher': self.page.get_cipher(account.number)},
        )
        return self.page.iter_investments()


class AXAAssuranceBrowser(AXAOldLoginBrowser):
    BASEURL = 'https://espaceclient.axa.fr'

    accounts = URL(r'/content/espace-client/accueil.content-inner.html', WealthAccountsPage)
    history = URL(r'/accueil/savings/savings/contract/_jcr_content.eccGetSavingsOperations.json', HistoryPage)
    history_investments = URL(
        r'/accueil/savings/savings/contract/_jcr_content.eccGetSavingOperationDetail.json',
        HistoryInvestmentsPage
    )
    details = URL(
        r'.*accueil/savings/(\w+)/contract',
        r'/#',
        AccountDetailsPage
    )

    investment = URL(r'/content/ecc-popin-cards/savings/[^/]+/repartition', InvestmentPage)
    investment_json = URL(
        r'https://espaceclient.axa.fr/content/espace-client/accueil/_jcr_content.savingsDistribution.json',
        InvestmentJsonPage
    )
    investment_monaxa = URL(r'https://monaxaweb-gp.axa.fr/MonAxa/Contrat/', InvestmentMonAxaPage)
    performance_monaxa = URL(r'https://monaxaweb-gp.axa.fr/MonAxa/ContratPerformance/', PerformanceMonAxaPage)

    documents_life_insurance = URL(
        r'/content/espace-client/accueil/mes-documents/contrats.content-inner.din_POLICY.html',
        DocumentsPage
    )
    documents_certificates = URL(
        r'/content/espace-client/accueil/mes-documents/attestations-d-assurances.content-inner.din_CERTIFICATE.html',
        DocumentsPage
    )
    documents_tax_area = URL(
        r'https://espaceclient.axa.fr/content/espace-client/accueil/mes-documents/espace-fiscal.content-inner.din_TAX.html',
        DocumentsPage
    )
    documents_membership_fee = URL(
        r'/content/espace-client/accueil/mes-documents/avis-d-echeance.content-inner.din_PREMIUM_STATEMENT.html',
        DocumentsPage
    )
    document_details = URL(
        r'/content/ecc-popin-cards/technical/detailed/dam-document.content-inner',
        DocumentDetailsPage
    )
    download = URL(
        r'/content/ecc-popin-cards/technical/detailed/download-document.downloadPdf.html',
        r'/content/dam/axa/ecc/pdf',
        DownloadPage
    )
    profile = URL(r'/content/ecc-popin-cards/transverse/userprofile.content-inner.html\?_=\d+', ProfilePage)

    def __init__(self, *args, **kwargs):
        super(AXAAssuranceBrowser, self).__init__(*args, **kwargs)

    def go_wealth_pages(self, account):
        self.location('/' + account.url)
        self.location(self.page.get_account_url(account.url))

    @need_login
    def iter_accounts(self):
        self.accounts.go()
        return self.page.iter_accounts()

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

        # return to espaceclient.axa.fr
        self.accounts.go()
        return invests

    @need_login
    def iter_investment(self, account):
        self.go_wealth_pages(account)
        self.investment_json.go(
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
            headers = {'Referer': 'https://espaceclient.axa.fr/accueil.html'}
            self.location(iframe_url, headers=headers)
            return self.iter_investment_monaxa(account)

        # No data available for this account.
        self.logger.warning('No investment URL available for account %s, investments cannot be retrieved.', account.id)
        return []

    @need_login
    def iter_history(self, account):
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

    @need_login
    def get_subscription_list(self):
        sub = Subscription()
        sub.label = sub.id = self.username
        yield sub

    @need_login
    def iter_documents(self, subscription):
        document_urls = [
            self.documents_life_insurance,
            self.documents_certificates,
            self.documents_tax_area,
            self.documents_membership_fee,
        ]
        for url in document_urls:
            url.go()
            for doc in self.page.get_documents(subid=subscription.id):
                yield doc

    @need_login
    def download_document(self, document):
        # "On request" documents are not downloadable, they are sent by physical mail
        if 'onrequest-document' in document.url:
            return
        # These documents have a direct download URL instead of a download ID.
        elif 'dam-document' in document.url:
            self.location(document.url)
            document_url = self.page.get_download_url()
            self.location(document_url)
            return self.page.content
        # These documents are obtained with a generic URL and a download ID as a parameter.
        elif document._download_id:
            self.download.go(data={'documentId': document._download_id})
            return self.page.content

    @need_login
    def get_profile(self):
        self.profile.go()
        return self.page.get_profile()
