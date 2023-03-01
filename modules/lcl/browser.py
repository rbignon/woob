# -*- coding: utf-8 -*-

# Copyright(C) 2010-2012  Romain Bignon, Pierre Mazière
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
import time
from datetime import datetime, timedelta, date
from functools import wraps
from urllib.parse import urlsplit, urlparse, parse_qs

import unidecode
from dateutil.relativedelta import relativedelta

from woob.exceptions import (
    BrowserIncorrectPassword, BrowserUnavailable, BrowserQuestion,
    AppValidation, AppValidationCancelled, AppValidationExpired,
    BrowserPasswordExpired,
)
from woob.browser import URL, need_login
from woob.browser.mfa import TwoFactorBrowser
from woob.browser.exceptions import ServerError, ClientError
from woob.capabilities.base import NotAvailable
from woob.capabilities.bank import (
    Account, AddRecipientBankError, AddRecipientStep, Recipient, AccountOwnerType,
    AccountOwnership,
)
from woob.tools.date import LinearDateGuesser
from woob.capabilities.base import find_object
from woob.tools.capabilities.bank.investments import create_french_liquidity
from woob.tools.value import Value

from .monespace.browser import MonEspaceBrowser
from .pages import (
    ErrorPage, LoginPage, AccountsPage, AccountHistoryPage, ContractsPage, ContractsChoicePage, BoursePage,
    AVPage, AVDetailPage, DiscPage, NoPermissionPage, RibPage, HomePage, LoansPage, TransferPage,
    AddRecipientPage, RecipientPage, SmsPage, RecipConfirmPage, RecipRecapPage, LoansProPage,
    Form2Page, DocumentsPage, ClientPage, SendTokenPage, CaliePage, ProfilePage, DepositPage,
    AVHistoryPage, AVInvestmentsPage, CardsPage, AVListPage, CalieContractsPage, RedirectPage,
    MarketOrdersPage, AVNotAuthorized, AVReroute, TwoFAPage, AuthentStatusPage, FinalizeTwoFAPage,
    PasswordExpiredPage, ContractRedirectionPage, MaintenancePage, CookiesAcceptancePage,
    RealEstateInvestmentsPage,
)


__all__ = ['LCLBrowser', 'LCLProBrowser']


# Browser
class LCLBrowser(TwoFactorBrowser):
    BASEURL = 'https://particuliers.secure.lcl.fr'
    STATE_DURATION = 15
    HAS_CREDENTIALS_ONLY = True

    login = URL(
        r'/outil/UAUT\?from=/outil/UWHO/Accueil/',
        r'/outil/UAUT\?from=.*',
        r'/outil/UWER/Accueil/majicER',
        r'/outil/UWER/Enregistrement/forwardAcc',
        r'https://assurance-vie-et-prevoyance.secure.lcl.fr/acces-non-authentifie',
        LoginPage
    )
    password_expired_page = URL(r'/outil/UWMC/NoConnect/incitationChangementMdp', PasswordExpiredPage)
    redirect_page = URL(r'/outil/UAUT/Accueil/preRoutageLogin', RedirectPage)
    contracts_page = URL(
        r'/outil/UAUT/Contrat/choixContrat.*',
        r'/outil/UAUT/Contract/getContract.*',
        r'/outil/UAUT/Contract/selectContracts.*',
        r'/outil/UAUT/Accueil/preRoutageLogin',
        ContractsPage)
    contract_redirection_page = URL(r'/outil/UAUT/Contract/redirection', ContractRedirectionPage)
    contracts_choice = URL(r'.*outil/UAUT/Contract/routing', ContractsChoicePage)
    error_page = URL(r'/outil/UAUT/Accueil/error', ErrorPage)
    home = URL(r'/outil/UWHO/Accueil/', HomePage)
    accounts = URL(r'/outil/UWSP/Synthese', AccountsPage)
    client = URL(r'/outil/uwho', ClientPage)
    history = URL(
        r'/outil/UWLM/ListeMouvements.*/acces(ListeMouvements|DetailsMouvement).*',
        r'/outil/UWLM/DetailMouvement.*/accesDetailMouvement.*',
        r'/outil/UWLM/Rebond',
        AccountHistoryPage)
    rib = URL(
        r'/outil/UWRI/Accueil/detailRib',
        r'/outil/UWRI/Accueil/listeRib',
        RibPage)
    finalrib = URL(r'/outil/UWRI/Accueil/', RibPage)

    cards = URL(
        r'/outil/UWCB/UWCBEncours.*/listeCBCompte.*',
        r'/outil/UWCB/UWCBEncours.*/listeOperations.*',
        CardsPage)

    skip = URL(
        r'/outil/UAUT/Contrat/selectionnerContrat.*',
        r'/index.html')

    no_perm = URL(r'/outil/UAUT/SansDroit/affichePageSansDroit.*', NoPermissionPage)

    bourse = URL(
        r'https://bourse.secure.lcl.fr/netfinca-titres/servlet/com.netfinca.frontcr.synthesis.HomeSynthesis',
        r'https://bourse.secure.lcl.fr/netfinca-titres/servlet/com.netfinca.frontcr.account.*',
        r'/outil/UWBO.*',
        BoursePage)

    market_orders = URL(
        r'https://bourse.secure.lcl.fr/netfinca-titres/servlet/com.netfinca.frontcr.order.OrderList',
        MarketOrdersPage
    )

    disc = URL(
        r'https://bourse.secure.lcl.fr/netfinca-titres/servlet/com.netfinca.frontcr.login.ContextTransferDisconnect',
        r'https://assurance-vie-et-prevoyance.secure.lcl.fr/filiale/entreeBam\?.*\btypeaction=reroutage_retour\b',
        r'https://assurance-vie-et-prevoyance.secure.lcl.fr/filiale/ServletReroutageCookie',
        r'/outil/UAUT/RetourPartenaire/retourCar',
        DiscPage)

    form2 = URL(r'/outil/UWVI/Routage', Form2Page)
    send_token = URL(r'/outil/UWVI/AssuranceVie/envoyerJeton', SendTokenPage)
    cookie_acceptance = URL(
        r'https://www.my-calie.fr/FO.HoldersWebSite/Cookies/CookiesAcceptance.aspx',
        CookiesAcceptancePage
    )
    calie_detail = URL(
        r'https://www.my-calie.fr/FO.HoldersWebSite/Disclaimer/Disclaimer.aspx.*',
        r'https://www.my-calie.fr/FO.HoldersWebSite/Contract/ContractDetails.aspx.*',
        r'https://www.my-calie.fr/FO.HoldersWebSite/Contract/ContractOperations.aspx.*',
        CaliePage)
    calie_contracts = URL(r'https://www.my-calie.fr/FO.HoldersWebSite/Contract/SearchContract.aspx', CalieContractsPage)

    assurancevie = URL(
        r'/outil/UWVI/AssuranceVie/accesSynthese',
        r'/outil/UWVI/AssuranceVie/accesDetail.*',
        AVPage)

    av_list = URL(r'https://assurance-vie-et-prevoyance.secure.lcl.fr/rest/assurance/synthesePartenaire', AVListPage)
    avdetail = URL(r'https://assurance-vie-et-prevoyance.secure.lcl.fr/consultation/epargne', AVDetailPage)
    av_history = URL(r'https://assurance-vie-et-prevoyance.secure.lcl.fr/rest/assurance/historique', AVHistoryPage)
    av_investments = URL(
        r'https://assurance-vie-et-prevoyance.secure.lcl.fr/rest/detailEpargne/contrat/(?P<life_insurance_id>\w+)',
        AVInvestmentsPage
    )
    av_access_not_authorized = URL(
        r'https://assurance-vie-et-prevoyance.secure.lcl.fr/acces-non-autorise',
        AVNotAuthorized
    )
    av_reroute = URL(
        r'https://assurance-vie-et-prevoyance.secure.lcl.fr/filiale/entreeBam\?typeaction=reroutage_retour',
        AVReroute
    )

    real_estate = URL(r'/outil/UWDI/', RealEstateInvestmentsPage)

    loans = URL(r'/outil/UWCR/SynthesePar/', LoansPage)
    loans_pro = URL(r'/outil/UWCR/SynthesePro/', LoansProPage)

    # Transfer / Add recipient
    transfer_page = URL(r'/outil/UWVS/', TransferPage)
    confirm_transfer = URL(r'/outil/UWVS/Accueil/redirectView', TransferPage)
    recipients = URL(r'/outil/UWBE/Consultation/list', RecipientPage)
    add_recip = URL(r'/outil/UWBE/Creation/creationSaisie', AddRecipientPage)
    recip_confirm = URL(r'/outil/UWAF/AuthentForteDesktop/authenticate', RecipConfirmPage)
    recip_confirm_validate = URL(r'/outil/UWAF/AuthentForteDesktop/confirmation', TwoFAPage)
    send_sms = URL(
        r'/outil/.*/Otp/envoiCodeOtp',
        r'/outil/.*/Otp/validationCodeOtp',
        SmsPage
    )
    recip_recap = URL(
        r'/outil/UWAF/AuthentForteDesktop/executionAction',
        r'/outil/UWBE/Creation/executeCreation',
        RecipRecapPage
    )

    # Bill
    documents = URL(
        r'/outil/UWDM/ConsultationDocument/derniersReleves',
        r'/outil/UWDM/Recherche/rechercherAll',
        DocumentsPage)
    documents_plus = URL(r'/outil/UWDM/Recherche/afficherPlus', DocumentsPage)

    profile = URL(r'/outil/UWIP/Accueil/rafraichir', ProfilePage)

    deposit = URL(
        r'/outil/UWPL/CompteATerme/accesSynthese',
        r'/outil/UWPL/DetailCompteATerme/accesDetail',
        DepositPage
    )

    # StrongAuth
    authent_status_page = URL(
        r'https://afafc.lcl.fr//wsafafc/api/v1/authentications/(?P<request_id>.*)/status\?_=(?P<timestamp>\w+)',
        AuthentStatusPage
    )
    twofa_page = URL(r'/outil/UWAF/AuthentForteDesktop/authenticate', TwoFAPage)
    finalize_twofa_page = URL(
        r'/outil/UWAF/AuthentForteDesktop/finalisation',
        FinalizeTwoFAPage
    )

    __states__ = ('contracts', 'current_contract', 'parsed_contracts')

    IDENTIFIANT_ROUTING = 'CLI'

    def __init__(self, config, *args, **kwargs):
        super(LCLBrowser, self).__init__(config, *args, **kwargs)
        self.accounts_list = None
        self.current_contract = None
        self.contracts = []
        self.parsed_contracts = False
        self.owner_type = AccountOwnerType.PRIVATE
        # `Mon espace` is LCL's new website, it's still not finished and users have the choice between it and
        # the legacy website. We have observed that some loans are only available in the new website.
        # Account IDs match between the legacy and the new website. Except for loans and cards.
        # for loans the old id can be reconstructed partially (cf. _legacy_id)
        # for cards it's not handled yet.
        self.mon_espace_browser = MonEspaceBrowser(config, *args, **kwargs)

        self.AUTHENTICATION_METHODS = {
            'resume': self.handle_polling,
            'code': self.handle_sms,
        }

    def load_state(self, state):
        if 'CodeOtp' in state.get('url', ''):
            state.pop('url')
        super(LCLBrowser, self).load_state(state)

    def init_login(self):
        assert isinstance(self.username, str)
        assert isinstance(self.password, str)

        if not self.password.isdigit():
            raise BrowserIncorrectPassword()

        # Since a while the virtual keyboard accepts only the first 6 digits of the password
        self.password = self.password[:6]

        # we force the browser to go to login page so it's work even
        # if the session expire
        # Must set the referer to avoid redirection to the home page
        self.login.go(headers={"Referer": "https://www.lcl.fr/"})
        try:
            self.page.login(self.username, self.password)
        except BrowserUnavailable:
            self.page.check_error()

        if self.response.status_code == 302:
            if 'AuthentForteDesktop' in self.response.headers['location']:
                # If we follow the redirection we will get a 2fa
                # The 2fa validation is crossbrowser
                self.check_interactive()
                self.twofa_page.go()
                if self.error_page.is_here():
                    error_message = self.page.get_error_message()
                    # In some rare cases, we are redirected here, with a message stating the connection failed
                    # Retrying at least an hour later solves the problem
                    if 'Echec de la connexion' in error_message:
                        raise BrowserUnavailable()
                    raise AssertionError('Reached error page.')
                self.two_factor_authentication()
            else:
                # If we're not redirected to 2fa page, it's likely to be the home page and we're logged in
                self.location(self.response.headers['location'])

        if self.login.is_here():
            self.page.check_error()

        if self.password_expired_page.is_here():
            raise BrowserPasswordExpired(self.page.get_message())

        if (not self.contracts and not self.parsed_contracts
           and (self.contracts_choice.is_here() or self.contracts_page.is_here())):
            # On the preRoutageLogin page we gather the list of available contracts for this account
            self.contracts = self.page.get_contracts_list()
            # If there is not multiple contracts then self.contracts will be empty
            if not self.contracts:
                self.page.select_contract()
            self.parsed_contracts = True

        self.accounts.stay_or_go()

    def two_factor_authentication(self):
        authent_mechanism = self.page.get_authent_mechanism()
        if authent_mechanism == 'otp_sms':
            phone = self.page.get_phone_attributes()

            # Send sms to user.
            data = {
                'telChoisi': phone['attr_id'],
                '_': int(round(time.time() * 1000)),
            }
            self.location('/outil/UWAF/Otp/envoiCodeOtp', params=data)

            if self.page.check_otp_error():
                raise BrowserQuestion(
                    Value(
                        'code',
                        label="Veuillez saisir le code qui vient d'être envoyé sur le numéro %s" % phone['number']
                    )
                )
        elif authent_mechanism == 'app_validation':
            if self.recip_confirm.is_here():
                self.recip_confirm_validate.go()
            msg = self.page.get_app_validation_msg()
            if not msg:
                msg = 'Veuillez valider votre connexion depuis votre application mobile LCL'
            raise AppValidation(msg)

        else:
            raise AssertionError("Strong authentication '%s' not handled" % authent_mechanism)

    def handle_polling(self):
        assert self.page, ('Handle_polling was called out of context, with no '
                           + 'previous page loaded, and so no decoupled was expected at this point')
        match = re.search(r'var requestId = "([^"]+)"', self.page.text)
        assert match, "request id not found in the javascript"
        request_id = match.group(1)

        timeout = time.time() + 300  # 5 minutes
        while time.time() < timeout:
            try:
                status = self.authent_status_page.go(
                    request_id=request_id,
                    timestamp=int(round(time.time() * 1000))  # current timestamp with millisecond
                ).get_status()
            except ClientError as e:
                if e.response.status_code == 400 and e.response.json()['codeError'] == "FCT_UID_UNKNOWN":
                    raise AppValidationExpired('La validation par application a expiré')
                raise
            if status == "VALID":
                self.finalize_twofa_page.go(params={'status': 'VALID'})
                break
            elif status == "CANCELLED":
                raise AppValidationCancelled()

            # on the website, the request is made every 5 seconds
            time.sleep(5)
        else:
            raise AppValidationExpired('La validation par application a expiré')

    def handle_sms(self):
        self.location('/outil/UWAF/Otp/validationCodeOtp?codeOtp=%s' % self.code)
        self.page.check_otp_error(otp_sent=True)

    def go_to_accounts(self):
        try:
            self.accounts.go()
        except ServerError as e:
            # Sometimes this page can return a 502 with a message "Pour raison de maintenance informatique,
            # votre espace « gestion de comptes » est momentanément indisponible. Nous vous invitons à vous
            # reconnecter ultérieurement. Nous vous prions de bien vouloir nous excuser pour la gêne occasionnée."
            if e.response.status_code == 502:
                maintenance_page = MaintenancePage(self, e.response)
                error_message = maintenance_page.get_message()
                if maintenance_page.get_error_code() == 'BPI-50':
                    raise BrowserUnavailable(error_message)
                raise AssertionError('An unexpected error occurred: %s' % error_message)
            raise

    @need_login
    def connexion_bourse(self):
        self.location('/outil/UWBO/AccesBourse/temporisationCar?codeTicker=TICKERBOURSECLI')
        if self.no_perm.is_here():
            return False
        next_page = self.page.get_next()
        if next_page:
            # go on a intermediate page to get a session cookie (jsessionid)
            self.location(next_page)
            # go to bourse page
            self.bourse.stay_or_go()
            return True

    def check_if_redirection_necessary(self):
        if self.contract_redirection_page.is_here() and self.page.should_submit_redirect_form():
            self.page.submit_redirect_form()

    def deconnexion_bourse(self):
        self.disc.stay_or_go()
        self.check_if_redirection_necessary()
        self.go_to_accounts()
        if self.login.is_here():
            # When we logout we can be disconnected from the main site
            self.do_login()

    @need_login
    def go_life_insurance_website(self):
        self.assurancevie.stay_or_go()
        life_insurance_routage_url = self.page.get_routage_url()
        if life_insurance_routage_url:
            self.location(life_insurance_routage_url)
            # check if the client has access to life insurance
            if self.av_access_not_authorized.is_here():
                # if not, reroute to the main website
                self.av_reroute.go()
            else:
                self.av_list.go()
                assert self.av_list.is_here(), 'Something went wrong while going to life insurances list page.'

    @need_login
    def update_life_insurance_account(self, life_insurance):
        self.av_investments.go(life_insurance_id=life_insurance.id)
        return self.page.update_life_insurance_account(life_insurance)

    @need_login
    def go_back_from_life_insurance_website(self):
        self.avdetail.stay_or_go()
        self.page.come_back()
        self.check_if_redirection_necessary()
        # Here we can sometimes be disconnected
        if self.login.is_here():
            self.do_login()

    def select_contract(self, id_contract):
        if self.current_contract and id_contract != self.current_contract:
            self.logger.debug('Changing contract to %s', id_contract)
            # when we go on bourse page, we can't change contract anymore... we have to logout.
            self.location('/outil/UAUT/Login/logout')
            # we already passed all checks on do_login so we consider it's ok.
            self.login.go().login(self.username, self.password)
            self.contracts_choice.go().select_contract(id_contract)

    def go_contract(f):
        @wraps(f)
        def wrapper(self, account, *args, **kwargs):
            self.select_contract(account._contract)
            return f(self, account, *args, **kwargs)
        return wrapper

    def check_accounts(self, account, from_monespace=False):
        # set from_monespace=True if the account was scrapped from the new website

        if from_monespace and account.type in (Account.TYPE_LOAN, Account.TYPE_CARD):
            # only loans and cards have different IDs than legacy website
            # we match based on label/balance
            return self.check_monespace_account(account)
        return all(account.id != acc.id for acc in self.accounts_list)

    def check_monespace_account(self, account):
        for acc in self.accounts_list:
            if acc.type != Account.TYPE_LOAN:
                continue
            if (
                (
                    acc.label == unidecode.unidecode(account.label)  # No accents in legacy website
                    and acc.balance == account.balance
                ) or unidecode.unidecode(account._legacy_id) in acc.id  # No accents in legacy website
            ):
                return False
        return True

    def update_accounts(self, account, from_monespace=False):
        if self.check_accounts(account, from_monespace=from_monespace):
            account._contract = self.current_contract
            account._is_monespace = False
            if from_monespace:
                account._is_monespace = True
            self.accounts_list.append(account)

    def set_deposit_account_id(self, account):
        self.deposit.go()
        if self.no_perm.is_here():
            self.logger.warning('Deposits are unavailable.')
        else:
            form = self.page.get_form(id='mainform')
            form['INDEX'] = account._link_index
            try:
                form.submit()
            except ServerError:
                # JS-forged message on the website
                raise BrowserUnavailable(
                    'Suite à un incident, nous ne pouvons donner suite à votre demande. Veuillez nous en excuser.'
                )
            else:
                self.page.set_deposit_account_id(account)

        self.deposit.go()

    @need_login
    def get_accounts(self):
        # This is required in case the browser is left in the middle of add_recipient and the session expires.
        if self.login.is_here():
            return self.get_accounts_list()

        profile_name = self.get_profile_name()
        if ' ' in profile_name:
            owner_name = re.search(r' (.+)', profile_name).group(1).upper()
        else:
            owner_name = profile_name.upper()

        # retrieve life insurance accounts
        self.assurancevie.stay_or_go()
        if self.no_perm.is_here():
            self.logger.warning('Life insurances are unavailable.')
        else:
            # retrieve life insurances from popups
            for a in self.page.get_popup_life_insurance(name=owner_name):
                self.update_accounts(a)

            # retrieve life insurances from calie website
            calie_index = self.page.get_calie_life_insurances_first_index()
            if calie_index:
                form = self.page.get_form(id="formRedirectPart")
                form['INDEX'] = calie_index
                form.submit()
                if self.cookie_acceptance.is_here():
                    self.page.handle_cookies()
                # if only one calie insurance, request directly leads to details on CaliePage
                if self.calie_detail.is_here():
                    self.page.check_error()
                    a = Account()
                    a.url = self.url
                    self.page.fill_account(obj=a)
                    self.update_accounts(a)
                # if several calie insurances, request leads to CalieContractsPage
                elif self.calie_contracts.is_here():
                    for a in self.page.iter_calie_life_insurance():
                        if a.url:
                            self.location(a.url)
                            self.page.fill_account(obj=a)
                            self.update_accounts(a)
                        else:
                            self.logger.warning('%s has no url to parse detail to' % a)
                # get back to life insurances list page
                self.assurancevie.stay_or_go()

            # retrieve life insurances on special lcl life insurance website
            if self.page.is_website_life_insurance():
                self.go_life_insurance_website()
                # check if av_list is here cause sometimes the user has not access to life insurance
                if self.av_list.is_here():
                    for life_insurance in self.page.iter_life_insurance():
                        life_insurance = self.update_life_insurance_account(life_insurance)
                        self.update_accounts(life_insurance)
                    self.go_back_from_life_insurance_website()

        # retrieve real_estate accounts
        self.go_to_accounts()
        self.real_estate.go()
        if self.no_perm.is_here():
            self.logger.warning('real estate are unavailable.')
        else:
            for account in self.page.iter_accounts(name=owner_name):
                account._is_monespace = False
                self.accounts_list.append(account)
        # retrieve accounts on main page
        self.go_to_accounts()
        for a in self.page.get_accounts_list(name=owner_name):
            if not self.check_accounts(a):
                continue

            self.location('/outil/UWRI/Accueil/')

            if self.no_perm.is_here():
                self.logger.warning('RIB is unavailable.')

            elif self.page.has_iban_choice():
                self.rib.go(data={'compte': '%s/%s/%s' % (a.id[0:5], a.id[5:11], a.id[11:])})
                if self.rib.is_here():
                    iban = self.page.get_iban()
                    if iban and a.id[11:] in iban:
                        a.iban = iban
                    else:
                        a.iban = NotAvailable

            else:
                iban = self.page.check_iban_by_account(a.id)
                if iban:
                    a.iban = iban
                else:
                    a.iban = NotAvailable

            self.update_accounts(a)

        # retrieve loans accounts
        self.loans.stay_or_go()
        if self.no_perm.is_here():
            self.logger.warning('Loans are unavailable.')
        else:
            for a in self.page.iter_loans():
                self.update_accounts(a)

        # retrieve pro loans accounts
        self.loans_pro.stay_or_go()
        if self.no_perm.is_here():
            self.logger.warning('Pro loans are unavailable.')
        else:
            for a in self.page.get_list():
                self.update_accounts(a)

        if self.connexion_bourse():
            for a in self.page.get_list(name=owner_name):
                self.update_accounts(a)
            self.deconnexion_bourse()
            # Disconnecting from bourse portal before returning account list
            # to be sure that we are on the banque portal

        # retrieve deposit accounts
        self.deposit.stay_or_go()
        if self.no_perm.is_here():
            self.logger.warning('Deposits are unavailable.')
        else:
            for a in self.page.get_list(name=owner_name):
                # There is no id on the page listing the 'Compte à terme'
                # So a form must be submitted to access the id of the contract
                self.set_deposit_account_id(a)
                self.update_accounts(a)

    @need_login
    def get_accounts_list(self):
        if self.accounts_list is None:
            self.accounts_list = []

            if self.contracts and self.current_contract:
                for id_contract in self.contracts:
                    self.select_contract(id_contract)
                    self.get_accounts()
            else:
                self.get_accounts()

        self.go_to_accounts()

        deferred_cards = self.page.get_deferred_cards()

        # We got deferred card page link and we have to go through it to get details.
        for account_id, link in deferred_cards:
            parent_account = find_object(self.accounts_list, id=account_id)
            self.location(link)
            # Url to go to each account card is made of agence id, parent account id,
            # parent account key id and an index of the card (0,1,2,3,4...).
            # This index is not related to any information, it's just an incremental integer
            for card_position, a in enumerate(self.page.get_child_cards(parent_account)):
                a._card_position = card_position
                self.update_accounts(a)

        profile_name = self.get_profile_name()
        if ' ' in profile_name:
            owner_name = re.search(r' (.+)', profile_name).group(1).upper()
        else:
            owner_name = profile_name.upper()

        for account in self.accounts_list:
            account.owner_type = self.owner_type
            self.set_ownership(account, owner_name)

        # As of today, the switch to monespace was not yet made
        # But there are clients with loans available only on the website and not the old one
        # we fetch these loans here.
        # TODO: uncomment this bit. monespace parsing is disabled temporarily until investigation is done.
        # monespace_accounts = self.get_monespace_accounts()
        # for acc in monespace_accounts:
        #     self.update_accounts(acc, from_monespace=True)

        return iter(self.accounts_list)

    def set_ownership(self, account, owner_name):
        if not account.ownership:
            if account.parent and account.parent.ownership:
                account.ownership = account.parent.ownership
            elif re.search(
                    r'(m|mr|me|mme|mlle|mle|ml)\.? (.*)\bou (m|mr|me|mme|mlle|mle|ml)\b(.*)',
                    account.label,
                    re.IGNORECASE
            ):
                account.ownership = AccountOwnership.CO_OWNER
            elif all(n in account.label for n in owner_name.split()):
                account.ownership = AccountOwnership.OWNER
            else:
                account.ownership = AccountOwnership.ATTORNEY

    def get_bourse_accounts_ids(self):
        bourse_accounts_ids = []
        for account in self.get_accounts_list():
            if 'bourse' in account.id:
                bourse_accounts_ids.append(account.id.split('bourse')[0])
        return bourse_accounts_ids

    def get_monespace_accounts(self):
        # It is ready to scrap all account types.
        # BUT if we want CARDS too we need to define, a MATCHING function betwee cards from the LEGACY and NEW websites
        # cf: check_account and check_monespace_account
        for account in self.mon_espace_browser.iter_accounts():
            if account.type == Account.TYPE_LOAN:
                yield account

    def get_monespace_history(self, account):
        return self.mon_espace_browser.iter_history(account)

    @go_contract
    @need_login
    def get_history(self, account):
        if account._is_monespace:
            yield from self.get_monespace_history(account)

        elif account._market_link:
            self.connexion_bourse()
            self.location(
                account._link_id, params={
                    'nump': account._market_id,
                }
            )
            self.page.get_fullhistory()

            for tr in self.page.iter_history():
                yield tr
            self.deconnexion_bourse()
        elif hasattr(account, '_link_id') and account._link_id:
            try:
                self.location(account._link_id)
            except ServerError:
                return
            if self.login.is_here():
                # Website crashed and we are disconnected.
                raise BrowserUnavailable()
            date_guesser = LinearDateGuesser()

            failed_threshold = 5
            failed_pages = 0
            for tr in self.page.get_operations(date_guesser=date_guesser):
                tr_page = None
                if (
                    hasattr(self.page, 'open_transaction_page')
                    and failed_pages < failed_threshold
                ):
                    # There are transactions details on a separate page (on the website, you click on the transaction, which opens an iframe).
                    # Unfortunately for some accounts, no details are available. Avoid opening a lot of bogus pages by stopping after a few failed ones.

                    tr_response = self.page.open_transaction_page(tr)
                    if tr_response:
                        tr_page = tr_response.page

                        if not tr_page or isinstance(tr_page, NoPermissionPage):
                            failed_pages += 1
                            self.logger.warning(
                                "failed to get transaction details page, failure count = %d",
                                failed_pages
                            )
                            if failed_pages >= failed_threshold:
                                self.logger.warning("failure threshold reached, not attempting to get transaction details anymore")
                        else:
                            if failed_pages:
                                self.logger.debug("resetting failed transaction details pages count")
                                failed_pages = 0

                self.page.fix_transaction_stuff(tr, tr_page)

                yield tr

        elif account.type == Account.TYPE_CARD:
            for tr in self.get_cb_operations(account=account, month=1):
                yield tr

        elif account.type == Account.TYPE_LIFE_INSURANCE:
            if not account._external_website:
                self.logger.warning('This account is limited, there is no available history.')
                return

            if account._is_calie_account:
                # TODO build parsing of history page, all-you-can-eat js in it
                # follow 'account._history_url' for that
                raise NotImplementedError()
            else:
                self.assurancevie.stay_or_go()
                self.go_life_insurance_website()
                assert self.av_list.is_here(), 'Something went wrong during iter life insurance history'
                # Need to be on account details page to do history request
                self.av_investments.go(life_insurance_id=account.id)
                self.av_history.go()
                for tr in self.page.iter_history():
                    yield tr
                self.go_back_from_life_insurance_website()

    @need_login
    def get_coming(self, account):
        if account.type == Account.TYPE_CARD:
            for tr in self.get_cb_operations(account=account, month=0):
                yield tr

    # %todo check this decorator : @go_contract
    @need_login
    def get_cb_operations(self, account, month=0):
        """
        Get CB operations.

        * month=0 : current operations (non debited)
        * month=1 : previous month operations (debited)
        """

        # Separation of bank account id and bank account key
        # example : 123456A
        regex = r'([0-9]{6})([A-Z]{1})'
        account_id_regex = re.match(regex, account.parent._compte)

        args = {
            'AGENCE': account.parent._agence,
            'COMPTE': account_id_regex.group(1),
            'CLE': account_id_regex.group(2),
            'NUMEROCARTE': account._card_position,
            'MOIS': month,
        }

        # We must go to '_cards_list' url first before transaction_link, otherwise, the website
        # will show same transactions for all account, despite different values in 'args'.
        assert 'MOIS=' in account._cards_list, 'Missing "MOIS=" in url'
        init_url = account._cards_list.replace('MOIS=0', 'MOIS=%s' % month)
        self.location(init_url)
        self.location(account._transactions_link, params=args)

        if month == 1:
            summary = self.page.get_card_summary()
            if summary:
                yield summary

        for tr in self.page.iter_transactions():
            # Strange behavior, but sometimes, rdate > date.
            # We skip it to avoid duplicate transactions.
            if tr.date >= tr.rdate:
                yield tr

    @go_contract
    @need_login
    def get_investment(self, account):
        if account.type == Account.TYPE_REAL_ESTATE:
            yield from account._investment

        elif account.type == Account.TYPE_LIFE_INSURANCE:
            if not account._external_website:
                self.logger.warning('This account is limited, there is no available investment.')
                return

            self.assurancevie.stay_or_go()
            if account._is_calie_account:
                calie_details = self.open(account.url)
                for inv in calie_details.page.iter_investment():
                    yield inv
            else:
                self.go_life_insurance_website()
                assert self.av_list.is_here(), 'Something went wrong during iter life insurance investments'
                self.av_investments.go(life_insurance_id=account.id)
                for inv in self.page.iter_investment():
                    yield inv
                self.go_back_from_life_insurance_website()

        elif account._market_link:
            self.connexion_bourse()
            self.location(account._market_link)
            yield from self.page.iter_investment(account_currency=account.currency)
            self.deconnexion_bourse()
        elif account.id in self.get_bourse_accounts_ids():
            yield create_french_liquidity(account.balance)

    def iter_market_orders(self, account):
        if account.type not in (Account.TYPE_MARKET, account.TYPE_PEA):
            return
        if account._market_link:
            try:
                # We go on the market space inside a try to make sure we go back to the base website.
                self.connexion_bourse()

                params = parse_qs(urlparse(account._market_link).query)
                params['ORDER_UPDDTMIN'] = (datetime.today() - relativedelta(years=1)).strftime('%d/%m/%Y')
                # Sort by creation instead of last update
                params['champsTri'] = 'CREATION_DT'

                index = 1
                last_page = 1

                while index < last_page + 1:
                    params['PAGE'] = index
                    self.market_orders.go(params=params)

                    # On the first page we check the total number of pages
                    if last_page == 1:
                        last_page = self.page.get_last_page_index()
                    index += 1

                    for order in self.page.iter_market_orders():
                        self.location(order._details_link)
                        self.page.fill_market_order(obj=order)
                        yield order
            finally:
                self.deconnexion_bourse()

    def finalize_new_recipient(self, recipient, **params):
        try:
            if 'code' in params:
                self.location('/outil/UWAF/Otp/validationCodeOtp?codeOtp=%s' % params['code'])
                self.page.check_otp_error(otp_sent=True)
                self.recip_recap.go()
            elif 'resume' in params:
                self.handle_polling()
        except BrowserIncorrectPassword as exc:
            raise AddRecipientBankError(
                message="%s" % exc
            )

        assert self.recip_recap.is_here(), 'If everything was ok, we should have arrived on the recip recap page.'
        error = self.page.get_error()
        if error:
            raise AddRecipientBankError(message=error)

        self.page.check_values(recipient.iban, recipient.label)
        return self.get_recipient_object(recipient.iban, recipient.label)

    def get_recipient_object(self, iban, label):
        r = Recipient()
        r.iban = iban
        r.id = iban
        r.label = label
        r.category = u'Externe'
        r.enabled_at = datetime.now().replace(microsecond=0) + timedelta(days=5)
        r.currency = u'EUR'
        r.bank_name = NotAvailable
        return r

    @need_login
    def init_new_recipient(self, recipient, **params):
        for _ in range(2):
            self.add_recip.go()
            if self.add_recip.is_here():
                break

        if self.no_perm.is_here() and self.page.get_error_msg():
            raise AddRecipientBankError(message=self.page.get_error_msg())

        assert self.add_recip.is_here(), 'Navigation failed: not on add_recip'

        error = self.page.get_error()
        if error:
            raise AddRecipientBankError(message=error)

        self.page.validate(recipient.iban, recipient.label)

        assert self.recip_confirm.is_here(), 'Navigation failed: not on recip_confirm'
        self.page.check_values(recipient.iban, recipient.label)

        new_recipient = self.get_recipient_object(recipient.iban, recipient.label)
        # We should arrive on a two factor authentication page to confirm that we want to do it
        try:
            self.two_factor_authentication()
        except BrowserQuestion as step:
            raise AddRecipientStep(new_recipient, *step.fields)
        except AppValidation as step:
            step.resource = new_recipient
            raise step

        # We will arrive here if two_factor_authentication didn't raise, and so 2fa was finally not needed
        self.recip_recap.go()
        return self.finalize_new_recipient(recipient)

    def new_recipient(self, recipient, **params):
        if 'code' in params or 'resume' in params:
            return self.finalize_new_recipient(recipient, **params)

        if recipient.iban[:2] not in ('FR', 'MC'):
            raise AddRecipientBankError(message="LCL n'accepte que les iban commençant par MC ou FR.")

        return self.init_new_recipient(recipient, **params)

    @go_contract
    @need_login
    def iter_recipients(self, origin_account):
        if origin_account._transfer_id is None:
            return
        self.transfer_page.go()
        if self.no_perm.is_here() or not self.page.can_transfer(origin_account._transfer_id):
            return
        self.page.choose_origin(origin_account._transfer_id)
        for recipient in self.page.iter_recipients(account_transfer_id=origin_account._transfer_id):
            yield recipient

    @go_contract
    @need_login
    def init_transfer(self, account, recipient, amount, reason=None, exec_date=None):
        self.transfer_page.go()
        self.page.choose_origin(account._transfer_id)
        self.page.choose_recip(recipient)

        if exec_date == date.today():
            self.page.transfer(amount, reason)
        else:
            self.page.deferred_transfer(amount, reason, exec_date)
        ret_transfer = self.page.handle_response(account, recipient)

        # Perform some security checks
        assert account.id == ret_transfer.account_id, (
            'account_id changed during transfer processing (from "%s" to "%s")'
            % (account.id, ret_transfer.account_id)
        )

        return ret_transfer

    @need_login
    def execute_transfer(self, transfer):
        self.page.confirm()
        self.page.check_confirmation()
        return transfer

    @need_login
    def get_advisor(self):
        return iter([self.accounts.stay_or_go().get_advisor()])

    @need_login
    def iter_subscriptions(self):
        self.client.go()
        # This contract redirection page happens in go_back_from_life_insurance_website and
        # deconnexion_bourse. Since we can't reproduce the bug, I am not sure if this will
        # repair anything. The log says 'ContractRedirectionPage' object has no attribute 'get_item'
        self.check_if_redirection_necessary()
        self.client.stay_or_go()
        yield self.page.get_item()

    @need_login
    def iter_documents(self, subscription):
        documents = []
        self.documents.go()
        self.documents_plus.go()
        self.page.do_search_request()
        for document in self.page.get_list():
            documents.append(document)
        return documents

    def get_profile_name(self):
        self.accounts.stay_or_go()
        return self.page.get_name()

    @need_login
    def get_profile(self):
        name = self.get_profile_name()
        # The self.get_profile_name() already does a
        # self.accounts.stay_or_go()
        self.profile.go(method="POST")
        profile = self.page.get_profile(name=name)
        return profile


class LCLProBrowser(LCLBrowser):
    BASEURL = 'https://professionnels.secure.lcl.fr'

    # We need to add this on the login form
    IDENTIFIANT_ROUTING = 'CLA'

    def __init__(self, *args, **kwargs):
        super(LCLProBrowser, self).__init__(*args, **kwargs)
        self.session.cookies.set("lclgen", "professionnels", domain=urlsplit(self.BASEURL).hostname)
        self.owner_type = AccountOwnerType.ORGANIZATION
