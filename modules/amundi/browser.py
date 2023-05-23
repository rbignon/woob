# Copyright(C) 2016      James GALT

# flake8: compatible
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

from uuid import uuid4
import re

from woob.browser import URL, LoginBrowser, need_login
from woob.capabilities.captcha import RecaptchaV2Question
from woob.exceptions import (
    BrowserIncorrectPassword, BrowserUserBanned, NotImplementedWebsite,
)
from woob.browser.exceptions import (
    ClientError, ServerError, BrowserHTTPNotFound,
)
from woob.capabilities.base import empty, NotAvailable
from woob.capabilities.bank import Account
from woob.tools.capabilities.bank.transactions import sorted_transactions
from woob.tools.captcha.virtkeyboard import VirtKeyboardError
from woob.tools.decorators import retry

from .pages import (
    AuthenticateFailsPage, ConfigPage, LoginPage, AccountsPage, AccountHistoryPage,
    AmundiInvestmentsPage, AllianzInvestmentPage, EEInvestmentPage, InvestmentPerformancePage,
    InvestmentDetailPage, EEProductInvestmentPage, ESAccountsPage, EresInvestmentPage, CprInvestmentPage,
    CprPerformancePage, BNPInvestmentPage, BNPInvestmentApiPage, AxaInvestmentPage, AxaInvestmentApiPage,
    EpsensInvestmentPage, EcofiInvestmentPage, SGGestionInvestmentPage,
    SGGestionPerformancePage, OlisnetInvestmentPage,
)


class AmundiBrowser(LoginBrowser):
    TIMEOUT = 120.0

    login = URL(r'public/login/virtualKeyboard', LoginPage)
    config_page = URL(r'public/config', ConfigPage)
    authenticate_fails = URL(r'public/authenticateFails', AuthenticateFailsPage)
    accounts = URL(r'api/individu/dispositifs\?flagUrlFicheFonds=true&codeLangueIso2=fr', AccountsPage)
    account_history = URL(
        r'api/individu/operations\?valeurExterne=false&filtreStatutModeExclusion=false&statut=CPTA',
        AccountHistoryPage,
    )

    # Amundi.fr investments
    amundi_investments = URL(r'https://www.amundi.fr/fr_part/product/view', AmundiInvestmentsPage)
    # EEAmundi browser investments
    ee_investments = URL(
        r'https://www.amundi-ee.com/part/home_fp&partner=PACTEO_SYS',
        r'https://funds.amundi-ee.com/productsheet/open/',
        EEInvestmentPage,
    )
    performance_details = URL(r'https://(.*)/ezjscore/call(.*)_tab_2', InvestmentPerformancePage)
    investment_details = URL(r'https://(.*)/ezjscore/call(.*)_tab_5', InvestmentDetailPage)
    # EEAmundi product investments
    ee_product_investments = URL(r'https://www.amundi-ee.com/product', EEProductInvestmentPage)
    # Allianz GI investments
    allianz_investments = URL(r'https://fr.allianzgi.com', AllianzInvestmentPage)
    # Eres investments
    eres_investments = URL(r'https://www.eres-group.com/eres/new_fiche_fonds.php', EresInvestmentPage)
    # CPR asset management investments
    cpr_investments = URL(r'https://www.cpr-am.fr/particuliers/product/view', CprInvestmentPage)
    cpr_performance = URL(r'https://www.cpr-am.fr/particuliers/ezjscore', CprPerformancePage)
    # BNP Paribas Epargne Retraite Entreprises
    bnp_investments = URL(
        r'https://www.epargne-retraite-entreprises.bnpparibas.com/entreprises/fonds',
        r'https://www.epargne-retraite-entreprises.bnpparibas.com/epargnants/fonds',
        BNPInvestmentPage,
    )
    bnp_investment_api = URL(
        r'https://www.epargne-retraite-entreprises.bnpparibas.com/api2/funds/overview/(?P<fund_id>.*)',
        BNPInvestmentApiPage,
    )
    # AXA investments
    axa_investments = URL(r'https://(.*).axa-im.fr/fonds', AxaInvestmentPage)
    axa_inv_api_redirection = URL(
        r'https://(?P<space>.*).axa-im.fr/o/fundscenter/api/funds/detail/header/fr_FR/(?P<fund_id>.*)',
        AxaInvestmentApiPage,
    )
    axa_inv_api = URL(
        r'https://(?P<space>.*).axa-im.fr/o/fundscenter/api/funds/detail/(?P<api_fund_id>.*)/performance/table/cumulative/fr_FR',
        AxaInvestmentApiPage,
    )
    # Epsens investments
    epsens_investments = URL(r'https://www.epsens.com/information-financiere', EpsensInvestmentPage)
    # Ecofi investments
    ecofi_investments = URL(r'http://www.ecofi.fr/fr/fonds/dynamis-solidaire', EcofiInvestmentPage)
    # Société Générale gestion investments
    sg_gestion_investments = URL(
        r'https://www.societegeneralegestion.fr/psSGGestionEntr/productsheet/view/idvm',
        SGGestionInvestmentPage,
    )
    sg_gestion_performance = URL(
        r'https://www.societegeneralegestion.fr/psSGGestionEntr/ezjscore/call',
        SGGestionPerformancePage,
    )
    # olisnet investments
    olisnet_investments = URL(r'https://ims.olisnet.com/extranet/(?P<action>).*', OlisnetInvestmentPage)

    def __init__(self, config, *args, **kwargs):
        super(AmundiBrowser, self).__init__(*args, **kwargs)
        self.config = config
        self.token_header = None

    def do_login(self):
        # Same uuid must be used for config_page and login page
        # config_page does not return anything useful for us but we must do
        # a GET request on it or we will have a 403 later on the login page
        uuid = str(uuid4())

        params = {
            "site": "m1st",
            "manufacturer": "Mozilla",
            "model": "X11",
            "platform": "web",
            "uuid": uuid,
            "version": "Linux Linux x86_64",
            "navigateur": "firefox",
            "navigateurVersion": "78.0.0",
        }

        self.config_page.go(params=params)

        # Check if account is temporarily blocked
        self.authenticate_fails.go(json={"username": self.username})
        connexion_status = self.response.json()
        if connexion_status == 3:
            raise BrowserUserBanned('Votre compte a été temporairement bloqué pour des raisons de sécurité (3 tentatives successives erronées).')

        # Hardcoded website_key because the HTML containing it is dynamically generated by JS
        website_key = '6LdBGWYUAAAAAK-5wpJNH0u1RrtIBVZI2xh1mixt'
        website_url = self.BASEURL
        captcha_response = self.config['captcha_response'].get()
        if not captcha_response:
            raise RecaptchaV2Question(website_key=website_key, website_url=website_url)

        data = {
            'site': 'm1st',
            'username': self.username,
            'password': self.password,
            'captcha': captcha_response,
            'uuid': uuid,
            'platform': 'web',
            'country': '',
            'city': '',
        }

        try:
            self.login.go(json=data)
            if 'epargnant.amundi' not in self.page.get_current_domain():
                # Able only to handle subspace behind domain 'epargnant.amundi'
                # TODO: handle amundi-ee.com/account website
                raise NotImplementedWebsite()
            self.token_header = {'X-noee-authorization': self.page.get_token()}
        except ClientError as e:
            if e.response.status_code == 401:
                message = e.response.json().get('message', '')
                # Wrong username
                if 'problem on profile for' in message.lower():
                    raise BrowserIncorrectPassword(message)

            # No other way to know if we have a wrong password
            if e.response.status_code == 403:
                raise BrowserIncorrectPassword()
            raise

    @staticmethod
    def merge_accounts(accounts):
        # merge accounts that have a master id to the master account
        master_accounts_list = []

        for account in accounts:
            if account._is_master:
                master_accounts_list.append(account)

        if not master_accounts_list:
            # There is no master_account.
            yield from [account for account in accounts if account.balance > 0]
            return

        for account in accounts:
            # If the account is not a PERCOL and has a positive balance,
            # we fetch it and check the next one.
            if account.type != Account.TYPE_PERCO and account.balance > 0:
                yield account
                continue

            # The account is a PERCOL with a positive balance.
            # Case 1: The account has no master and is not a master.
            elif account.balance > 0 and not account._is_master and not account._master_id:
                yield account
                continue

            for master_account in master_accounts_list:
                # Case 2: The account has a master account but both of them got a positive balance.
                # We need to remove "Piloté" or "Libre" from the master account label.
                if all((
                    account._master_id == master_account._id_dispositif,
                    account.balance > 0,
                    master_account.balance > 0,
                    ('Piloté' in account.label and 'Libre' in master_account.label)
                    or ('Piloté' in master_account.label and 'Libre' in account.label),
                )):
                    master_account.label = re.sub(r' Piloté| Libre', '', master_account.label)

                # Case 3: The account has a master.
                if account.balance > 0 and account._master_id == master_account._id_dispositif:
                    master_account._sub_accounts.append(account)

        for master_account in master_accounts_list:
            # If the master account has a balance of 0, we need to assign the first sub_account id
            # with a positive balance to replace the original master account id.
            # Otherwise, the PSU would be unable to access the master account
            # if this account was previously 'deactivated' due to a balance of 0.
            if master_account.balance == 0:
                for account in master_account._sub_accounts:
                    master_account.id = account.id
                    break

            # We aggregate the master account with all his sub_accounts.
            for account in master_account._sub_accounts:
                master_account.balance += account.balance

            if master_account.balance > 0:
                yield master_account

    @need_login
    def iter_accounts(self):
        self.accounts.go(headers=self.token_header)
        company_name = self.page.get_company_name()
        if empty(company_name):
            self.logger.warning('Could not find the company name for these accounts.')

        accounts = list(self.page.iter_accounts(username=self.username))

        # We need to store the existing link between active PEEs and disabled ones.
        # Empty PEEs (balance to 0) can have transactions that we need to retrieve.
        # Since empty PEEs are ignored, if it's linked to an active PEE, we need to
        # transfer his history in the active linked account.
        for account in accounts:
            # We only retrieve link of PEE accounts with null balances.
            if all((
                account._code_dispositif_lie,
                account.balance == 0,
                account.type == Account.TYPE_PEE,
            )):
                for acc in accounts:
                    if acc.balance > 0 and account._code_dispositif_lie == acc.id:
                        acc._linked_accounts.append(account.id)

        for account in self.merge_accounts(accounts):
            account.company_name = company_name
            yield account

    @need_login
    def iter_investment(self, account):
        if account.balance == 0:
            self.logger.info('Account %s has a null balance, no investment available.', account.label)
            return
        self.accounts.stay_or_go(headers=self.token_header)

        ignored_urls = (
            'www.sggestion-ede.com/product',  # Going there leads to a 404
            'www.assetmanagement.hsbc.com',  # Information not accessible
            'www.labanquepostale-am.fr/nos-fonds',  # Nothing interesting there
        )

        handled_urls = (
            'www.amundi.fr/fr_part',  # AmundiInvestmentsPage
            'funds.amundi-ee.com/productsheet',  # EEInvestmentDetailPage & EEInvestmentPerformancePage
            'www.amundi-ee.com/part/home_fp',  # EEInvestmentDetailPage & EEInvestmentPerformancePage
            'www.amundi-ee.com/product',  # EEProductInvestmentPage
            'fr.allianzgi.com/fr-fr',  # AllianzInvestmentPage
            'www.eres-group.com/eres',  # EresInvestmentPage
            'www.cpr-am.fr/particuliers/product',  # CprInvestmentPage
            'www.epargne-retraite-entreprises.bnpparibas.com',  # BNPInvestmentPage
            'axa-im.fr/fonds',  # AxaInvestmentPage
            'www.epsens.com/information-financiere',  # EpsensInvestmentPage
            'www.ecofi.fr/fr/fonds/dynamis-solidaire',  # EcofiInvestmentPage
            'www.societegeneralegestion.fr',  # SGGestionInvestmentPage
            'https://ims.olisnet.com/extranet',  # OlisnetInvestmentPage
        )

        def aggregate_investments(investments):
            # Aggregate investments with the same label within the same account.
            aggregated_investments = dict()
            for inv in investments:
                existing_investment = aggregated_investments.get(inv.label)
                if existing_investment:
                    existing_investment.valuation += inv.valuation
                    if not empty(existing_investment.quantity):
                        existing_investment.quantity += inv.quantity
                    if not empty(existing_investment.diff):
                        existing_investment.diff += inv.diff
                else:
                    aggregated_investments[inv.label] = inv
                    yield inv

        def iter_investment_from_account(account):
            for inv in self.page.iter_investments(account_id=account.id, account_type=account.type):
                if inv._details_url:
                    # Only go to known details pages to avoid logout on unhandled pages
                    if any(url in inv._details_url for url in handled_urls):
                        self.fill_investment_details(inv)
                    else:
                        if not any(url in inv._details_url for url in ignored_urls):
                            # Not need to raise warning if the URL is already known and ignored
                            self.logger.warning('Investment details on URL %s are not handled yet.', inv._details_url)
                        inv.asset_category = NotAvailable
                        inv.recommended_period = NotAvailable
                yield inv

        investments = []
        account_ids = []
        if account._is_master and account._sub_accounts:
            for sub_account in account._sub_accounts:
                account_ids.append(sub_account.id)
                if sub_account.balance == 0:
                    self.logger.info('Account %s has a null balance, no investment available.', sub_account.label)
                    continue

                investments.extend(list(iter_investment_from_account(sub_account)))
                self.accounts.stay_or_go(headers=self.token_header)

        if account.id not in account_ids:
            investments.extend(list(iter_investment_from_account(account)))

        return aggregate_investments(investments)

    @need_login
    def fill_investment_details(self, inv):
        # Going to investment details may lead to various websites.
        # This method handles all the already encountered pages.
        try:
            self.location(inv._details_url)
        except (ServerError, BrowserHTTPNotFound):
            # Some URLs return a 500 or a 404 even on the website
            self.logger.warning('Details are not available for this investment.')
            inv.asset_category = NotAvailable
            inv.recommended_period = NotAvailable
            return inv

        # Pages with only asset category available
        if self.allianz_investments.is_here():
            inv.asset_category = self.page.get_asset_category()
            inv.recommended_period = NotAvailable

        # Pages with asset_category & perfomance
        if self.axa_investments.is_here():
            params = self.page.get_redirection_params()
            fund_id = re.search(r'(\d+)', self.url.split('-')[-1]).group(1)
            space = re.search(r'https:\/\/(\w+).axa', self.url).group(1)
            self.axa_inv_api_redirection.go(space=space, fund_id=fund_id, params=params)

            self.page.get_asset_category(obj=inv)

            api_fund_id = self.page.get_api_fund_id()
            self.axa_inv_api.go(space=space, api_fund_id=api_fund_id)

            self.page.fill_investment(obj=inv)

        # Pages with asset category & recommended period
        elif any((
            self.eres_investments.is_here(),
            self.ee_product_investments.is_here(),
            self.epsens_investments.is_here(),
            self.ecofi_investments.is_here(),
        )):
            self.page.fill_investment(obj=inv)

        # Particular cases
        elif (
            self.ee_investments.is_here()
            or self.amundi_investments.is_here()
        ):
            if self.ee_investments.is_here():
                inv.recommended_period = self.page.get_recommended_period()
            details_url = self.page.get_details_url()
            performance_url = self.page.get_performance_url()
            if details_url:
                self.location(details_url)
                if self.investment_details.is_here():
                    inv.recommended_period = inv.recommended_period or self.page.get_recommended_period()
                    inv.asset_category = self.page.get_asset_category()
            if performance_url:
                self.location(performance_url)
                if self.performance_details.is_here():
                    # The investments JSON only contains 1 & 5 years performances
                    # If we can access EEInvestmentPerformancePage, we can fetch all three
                    # values (1, 3 and 5 years), in addition the values are more accurate here.
                    complete_performance_history = self.page.get_performance_history()
                    if complete_performance_history:
                        inv.performance_history = complete_performance_history

        elif (
            self.sg_gestion_investments.is_here()
            or self.cpr_investments.is_here()
        ):
            # Fetch asset category & recommended period
            self.page.fill_investment(obj=inv)
            # Fetch all performances on the details page
            performance_url = self.page.get_performance_url()
            if performance_url:
                self.location(performance_url)
                complete_performance_history = self.page.get_performance_history()
                if complete_performance_history:
                    inv.performance_history = complete_performance_history

        elif self.bnp_investments.is_here():
            # We fetch the fund ID and get the attributes directly from the BNP-ERE API
            fund_id = self.page.get_fund_id()
            if fund_id:
                # Specify the 'Accept' header otherwise the server returns WSDL instead of JSON
                self.bnp_investment_api.go(fund_id=fund_id, headers={'Accept': 'application/json'})
                self.page.fill_investment(obj=inv)
            else:
                self.logger.warning('Could not fetch the fund_id for BNP investment %s.', inv.label)
                inv.asset_category = NotAvailable
                inv.recommended_period = NotAvailable

        elif self.olisnet_investments.is_here():
            graph_id = self.page.get_graph_id()
            self.olisnet_investments.go(action='benchmark.jsp')
            inv.performance_history[5] = self.page.get_performance()

            for year in (1, 3):
                self.olisnet_investments.go(action='duree.jsp', params={'cs': graph_id, 'duree': f'{year}a'})
                self.olisnet_investments.go(action='benchmark.jsp')
                inv.performance_history[year] = self.page.get_performance()

        return inv

    @need_login
    def iter_pockets(self, account):
        if account.balance == 0:
            self.logger.info('Account %s has a null balance, no pocket available.', account.label)
            return

        self.accounts.stay_or_go(headers=self.token_header)

        def iter_pocket_from_account(account):
            for investment in self.page.iter_investments(account_id=account.id, account_type=account.type):
                for pocket in investment._pockets:
                    pocket.investment = investment
                    pocket.label = investment.label
                    yield pocket

        if account._is_master and account._sub_accounts:
            sub_accounts_id = []
            for sub_account in account._sub_accounts:
                sub_accounts_id.append(sub_account.id)
                yield from iter_pocket_from_account(sub_account)
            if account.id not in sub_accounts_id:
                # Master account haven't a sub-account for itself
                # We have to fetch pocket directly
                yield from iter_pocket_from_account(account)
        else:
            yield from iter_pocket_from_account(account)

    @need_login
    def iter_history(self, account):
        self.account_history.go(headers=self.token_header)
        transactions = []

        if account._is_master:
            for sub_account in account._sub_accounts:
                for tr in self.page.iter_history(account=sub_account):
                    if tr not in transactions:
                        transactions.append(tr)

        for tr in self.page.iter_history(account=account):
            if tr not in transactions:
                transactions.append(tr)

        return sorted_transactions(transactions)

class EEAmundi(AmundiBrowser):
    # Careful if you modify the BASEURL, also verify Amundi's Children modules
    BASEURL = 'https://epargnant.amundi-ee.com/'


class TCAmundi(AmundiBrowser):
    # Careful if you modify the BASEURL, also verify Amundi's Children modules
    BASEURL = 'https://epargnant.amundi-tc.com/'


class CAAmundi(AmundiBrowser):
    # Careful if you modify the BASEURL, also verify Amundi's Children modules
    BASEURL = 'https://epargnant.amundi-ca-assurances.com/'


class ESAmundi(AmundiBrowser):
    # Careful if you modify the BASEURL, also verify Amundi's Children modules
    BASEURL = 'https://www.amundi-ee.com/account/'

    keyboard = URL(r'public/virtualKeyboard', LoginPage)
    login = URL(r'public/authenticate', LoginPage)
    accounts = URL(
        r'api/individu/positionsFonds\?inclurePositionVide=false&flagUrlFicheFonds=true',
        ESAccountsPage,
    )

    @retry(VirtKeyboardError, delay=0)
    def get_vk_password(self):
        """ Transform password to vk_password

        Vk image is sent in base64.
        For each keyboard the numbers are formatted in a unique style.
        So if we download an unknown vk, VirtKeyboardError is raised
        and we will retry with another vk.
        If VirtKeyboardError happens too often, please add more
        vk image in ESAmundiVirtKeyboard.
        """
        self.keyboard.go()

        keyboard = self.page.get_keyboard()
        vk_password = self.page.create_vk_password(self.password, keyboard)
        return keyboard, vk_password

    def do_login(self):
        captcha_response = self.config['captcha_response'].get()
        if not captcha_response:
            self.go_home()
            self.config_page.go()
            captcha_key = self.page.get_captcha_key()
            raise RecaptchaV2Question(website_key=captcha_key, website_url=self.BASEURL)

        keyboard, vk_password = self.get_vk_password()

        json_data = {
            'captcha': captcha_response,
            'idKeyboard': keyboard['id'],
            'password': vk_password,
            'username': self.username,
        }
        try:
            self.login.go(json=json_data)
        except ClientError as err:
            # Absolutely no way to know which json_data field is wrong
            if err.response.status_code == 403:
                raise BrowserIncorrectPassword()
            raise

        self.token_header = {'X-noee-authorization': self.page.get_token()}
