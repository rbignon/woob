# -*- coding: utf-8 -*-

# Copyright(C) 2012-2019  Budget Insight
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

# flake8: compatible

from __future__ import unicode_literals

from datetime import datetime, timedelta
from decimal import Decimal
import re

from weboob.capabilities.wealth import Per, PerProviderType
from weboob.capabilities.bank import (
    Account, Loan, Transaction, AccountNotFound, RecipientNotFound,
    AddRecipientStep, RecipientInvalidOTP, RecipientInvalidIban,
    AddRecipientBankError,
)
from weboob.capabilities.base import empty, NotAvailable, strict_find_object
from weboob.browser import LoginBrowser, URL, need_login, StatesMixin
from weboob.browser.exceptions import ServerError, ClientError, BrowserHTTPNotFound, HTTPNotFound
from weboob.exceptions import (
    BrowserUnavailable, BrowserIncorrectPassword, ActionNeeded,
    AuthMethodNotImplemented,
)
from weboob.tools.capabilities.bank.iban import is_iban_valid
from weboob.tools.capabilities.bank.transactions import sorted_transactions
from weboob.tools.decorators import retry
from weboob.tools.value import Value
from weboob.tools.capabilities.bank.investments import create_french_liquidity
from weboob.tools.compat import parse_qs, urlparse, urljoin

from .pages import (
    LoginPage, LoggedOutPage, KeypadPage, SecurityPage, ContractsPage, FirstConnectionPage, AccountsPage,
    AccountDetailsPage, TokenPage, ChangePasswordPage, IbanPage, HistoryPage, CardsPage, CardHistoryPage,
    NetfincaRedirectionPage, NetfincaHomePage, PredicaRedirectionPage, PredicaInvestmentsPage,
    LifeInsuranceInvestmentsPage, BgpiRedirectionPage, BgpiAccountsPage, BgpiInvestmentsPage,
    ProfilePage, ProfileDetailsPage, ProProfileDetailsPage,
)
from .transfer_pages import (
    RecipientsPage, TransferPage, TransferTokenPage, NewRecipientPage,
    NewRecipientSmsPage, SendSmsPage, ValidateSmsPage, RecipientTokenPage,
    VerifyNewRecipientPage, ValidateNewRecipientPage, CheckSmsPage,
    EndNewRecipientPage,
)

from .netfinca_browser import NetfincaBrowser

__all__ = ['CreditAgricoleBrowser']


class CreditAgricoleBrowser(LoginBrowser, StatesMixin):
    # Login pages
    login_page = URL(r'particulier/acceder-a-mes-comptes.html$', LoginPage)
    keypad = URL(r'particulier/acceder-a-mes-comptes.authenticationKeypad.json', KeypadPage)
    security_check = URL(r'particulier/acceder-a-mes-comptes.html/j_security_check', SecurityPage)
    first_connection = URL(r'.*/operations/interstitielles/premiere-connexion.html', FirstConnectionPage)
    token_page = URL(r'libs/granite/csrf/token.json', TokenPage)
    change_password = URL(r'(?P<space>[\w-]+)/operations/interstitielles/code-personnel.html', ChangePasswordPage)

    # Accounts pages
    contracts_page = URL(
        r'(?P<space>[\w-]+)/operations/.rechargement.contexte.html\?idBamIndex=(?P<id_contract>)', ContractsPage
    )

    accounts_page = URL(r'[\w-]+/operations/synthese.html', AccountsPage)

    account_details = URL(
        r'(?P<space>[\w-]+)/operations/synthese/jcr:content.produits-valorisation.json/(?P<category>)',
        AccountDetailsPage
    )

    account_iban = URL(
        r'(?P<space>[\w-]+)/operations/operations-courantes/editer-rib/jcr:content.ibaninformation.json', IbanPage
    )

    cards = URL(r'(?P<space>[\w-]+)/operations/(?P<op>.*)/mes-cartes/jcr:content.listeCartesParCompte.json', CardsPage)

    history = URL(r'(?P<space>[\w-]+)/operations/synthese/detail-comptes/jcr:content.n3.operations.json', HistoryPage)

    card_history = URL(
        r'(?P<space>[\w-]+)/operations/synthese/detail-comptes/jcr:content.n3.operations.encours.carte.debit.differe.json',
        CardHistoryPage
    )

    # Investment pages
    life_insurance_investments = URL(
        r'(?P<space>[\w-]+)/operations/synthese/detail-assurance-vie.html\?idx=(?P<idx>\d+)&famillecode=(?P<category>\d+)',
        LifeInsuranceInvestmentsPage
    )

    netfinca_redirection = URL(
        r'(?P<space>[\w-]+)/operations/moco/catitres/_?jcr[:_]content.init.html', NetfincaRedirectionPage
    )
    netfinca_home = URL(
        r'https://www.cabourse.credit-agricole.fr/netfinca-titres/servlet/com.netfinca.frontcr.navigation.AccueilBridge',
        NetfincaHomePage
    )

    predica_redirection = URL(
        r'(?P<space>[\w-]+)/operations/moco/predica/_?jcr[:_]content.init.html', PredicaRedirectionPage
    )
    predica_investments = URL(
        r'https://npcprediweb.predica.credit-agricole.fr/rest/detailEpargne/contrat/', PredicaInvestmentsPage
    )

    bgpi_redirection = URL(r'(?P<space>[\w-]+)/operations/moco/bgpi/_?jcr[:_]content.init.html', BgpiRedirectionPage)
    bgpi_accounts = URL(r'https://bgpi-gestionprivee.credit-agricole.fr/bgpi/Logon.do', BgpiAccountsPage)
    bgpi_investments = URL(r'https://bgpi-gestionprivee.credit-agricole.fr/bgpi/CompteDetail.do', BgpiInvestmentsPage)

    # Profile pages
    profile_page = URL(r'(?P<space>[\w-]+)/operations/synthese/jcr:content.npc.store.client.json', ProfilePage)

    profile_details = URL(
        r'(?P<space>[\w-]+)/operations/profil/infos-personnelles/gerer-coordonnees.html', ProfileDetailsPage
    )

    pro_profile_details = URL(
        r'(?P<space>[\w-]+)/operations/profil/infos-personnelles/controler-coordonnees.html', ProProfileDetailsPage
    )

    # Recipients pages
    recipients = URL(r'(?P<space>.*)/operations/(?P<op>.*)/virement/jcr:content.accounts.json', RecipientsPage)
    transfer_token = URL(
        r'(?P<space>.*)/operations/(?P<op>.*)/virement.npcgeneratetoken.json\?tokenTypeId=1', TransferTokenPage
    )
    transfer = URL('(?P<space>.*)/operations/(?P<op>.*)/virement/jcr:content.check-transfer.json', TransferPage)
    transfer_recap = URL(
        r'(?P<space>.*)/operations/(?P<op>.*)/virement/jcr:content.transfer-data.json\?useSession=true', TransferPage
    )

    transfer_exec = URL('(?P<space>.*)/operations/(?P<op>.*)/virement/jcr:content.process-transfer.json', TransferPage)

    add_new_recipient = URL(
        r'(?P<space>.*)/operations/operations-courantes/gerer-beneficiaires/ajouter-modifier-beneficiaires.html',
        NewRecipientPage
    )
    new_recipient_sms = URL(
        r'(?P<space>.*)/operations/authentification-forte/sms.otp.html\?transactionId=(?P<transaction_id>.*)',
        NewRecipientSmsPage
    )
    verify_new_recipient = URL(
        r'(?P<space>.*)/operations/operations-courantes/gerer-beneficiaires/ajouter-modifier-beneficiaires/jcr:content.verifier_donnees_beneficiaires.json\?transactionId=(?P<transaction_id>.*)',
        VerifyNewRecipientPage
    )
    validate_new_recipient = URL(
        r'(?P<space>.*)/operations/operations-courantes/gerer-beneficiaires/ajouter-modifier-beneficiaires/jcr:content.validation.json\?transactionId=(?P<transaction_id>.*)',
        ValidateNewRecipientPage
    )
    end_new_recipient = URL(
        r'(?P<space>.*)/operations/operations-courantes/gerer-beneficiaires.html\?transactionId=(?P<transaction_id>.*)',
        EndNewRecipientPage
    )

    send_sms = URL(r'(?P<space>.*)/operations/authentification-forte/sms/jcr:content.send.json', SendSmsPage)
    validate_sms = URL(
        r'(?P<space>.*)/operations/authentification-forte/sms/jcr:content.validation.json', ValidateSmsPage
    )
    check_sms = URL(
        r'(?P<space>.*)/operations/authentification-forte/sms.success.html\?transactionId=(?P<transaction_id>.*)',
        CheckSmsPage
    )
    recipient_token = URL(
        r'(?P<space>.*)/operations/operations-courantes/gerer-beneficiaires/ajouter-modifier-beneficiaires.npcgeneratetoken.json\?transactionId=(?P<transaction_id>.*)&tokenTypeId=3',
        RecipientTokenPage
    )
    logged_out = URL(r'.*', LoggedOutPage)

    __states__ = ('BASEURL', 'transaction_id', 'sms_csrf_token', 'need_reload_state', 'accounts_url')

    def __init__(self, website, *args, **kwargs):
        super(CreditAgricoleBrowser, self).__init__(*args, **kwargs)
        self.website = website
        self.accounts_url = None
        self.total_spaces = None

        # Netfinca browser:
        self.weboob = kwargs.pop('weboob')
        dirname = self.responses_dirname
        if dirname:
            dirname += '/netfinca'
        self.netfinca = NetfincaBrowser(
            '', '', logger=self.logger, weboob=self.weboob, responses_dirname=dirname, proxy=self.PROXIES
        )

        # Needed to add a new recipient
        self.transaction_id = None
        self.sms_csrf_token = None
        self.need_reload_state = None

    def load_state(self, state):
        # Reload state for AddRecipientStep only
        if state.get('need_reload_state'):
            # Do not locate_browser for 2fa
            state.pop('url', None)
            super(CreditAgricoleBrowser, self).load_state(state)
            self.need_reload_state = None

    @property
    def space(self):
        return self.session.cookies.get('marche', None)

    def deinit(self):
        super(CreditAgricoleBrowser, self).deinit()
        self.netfinca.deinit()

    @retry(BrowserUnavailable)
    def do_security_check(self):
        try:
            form = self.get_security_form()
            self.security_check.go(data=form)
        except ServerError as exc:
            # Wrongpass returns a 500 server error...
            exc_json = exc.response.json()
            error = exc_json.get('error')
            if error:
                message = error.get('message', '')
                wrongpass_messages = ("Votre identification est incorrecte", "Vous n'avez plus droit")
                if any(value in message for value in wrongpass_messages):
                    raise BrowserIncorrectPassword()
                if 'obtenir un nouveau code' in message:
                    raise ActionNeeded(message)

                code = error.get('code', '')
                technical_error_messages = ('Un incident technique', 'identifiant et votre code personnel')
                # Sometimes there is no error message, so we try to use the code as well
                technical_error_codes = ('technical_error',)
                if (
                    any(value in message for value in technical_error_messages)
                    or any(value in code for value in technical_error_codes)
                ):
                    raise BrowserUnavailable(message)

            # When a PSD2 SCA is required it also returns a 500, hopefully we can detect it
            if (
                exc_json.get('url') == 'dsp2/informations.html'
                or exc_json.get('redirection', '').endswith('dsp2/informations.html')
            ):
                return self.handle_sca()

            raise

    def do_login(self):
        if not self.username or not self.password:
            raise BrowserIncorrectPassword()

        # For historical reasons (old cragr website), the websites look like 'www.ca-region.fr',
        # from which we extract 'ca-region' to construct the BASEURL with a format such as:
        # 'https://www.credit-agricole.fr/ca-region/'
        region_domain = re.sub(r'^www\.', 'www.credit-agricole.fr/', self.website.replace('.fr', ''))
        self.BASEURL = 'https://%s/' % region_domain

        self.login_page.go()
        self.do_security_check()

        # accounts_url may contain '/particulier', '/professionnel', '/entreprise', '/agriculteur' or '/association'
        accounts_url = self.page.get_accounts_url()
        assert accounts_url, 'Could not get accounts url from security check'

        # It is important to set the domain otherwise self.location(self.accounts_url)
        # will crash when called from external domains (Predica, Netfinca, Bgpi...)
        self.accounts_url = urljoin(self.url, accounts_url)
        try:
            self.location(self.accounts_url)
        except HTTPNotFound:
            # Sometimes the url the json sends us back is just unavailable...
            raise BrowserUnavailable()

        assert self.accounts_page.is_here(), (
            'We failed to login after the security check: response URL is %s' % self.url
        )
        # Once the security check is passed, we are logged in.

    def handle_sca(self):
        """
        The ActionNeeded is temporary: we are waiting for an account to implement the SCA.
        We can raise an ActionNeed because a validated SCA is cross web browser: if user performs
        the SCA on its side there will be no SCA anymore on weboob.
        """
        raise ActionNeeded('Vous devez réaliser la double authentification sur le portail internet')

    def get_security_form(self):
        headers = {'Referer': self.BASEURL + 'particulier/acceder-a-mes-comptes.html'}
        data = {'user_id': self.username}
        self.keypad.go(headers=headers, data=data)

        keypad_password = self.page.build_password(self.password[:6])
        keypad_id = self.page.get_keypad_id()
        assert keypad_password, 'Could not obtain keypad password'
        assert keypad_id, 'Could not obtain keypad id'
        self.login_page.go()
        # Get the form data to POST the security check:
        form = self.page.get_login_form(self.username, keypad_password, keypad_id)
        return form

    def get_account_iban(self, account_index, account_category, weboob_account_id):
        """
        Fetch an IBAN for a given account
        It may fail from time to time (error 500 or 403)
        """
        params = {
            'compteIdx': int(account_index),
            'grandeFamilleCode': int(account_category),
        }
        try:
            self.account_iban.go(space=self.space, params=params)
        except (ClientError, ServerError):
            self.logger.warning('Request to IBAN failed for account id "%s"', weboob_account_id)
            return NotAvailable

        iban = self.page.get_iban()
        if is_iban_valid(iban):
            return iban
        return NotAvailable

    @need_login
    def check_space_connection(self, contract):
        # Going to a specific space often returns a 500 error
        # so we might have to retry several times.
        try:
            self.go_to_account_space(contract)
        except (ServerError, BrowserUnavailable):
            self.logger.warning('Server returned error 500 when trying to access space %s, we try again', contract)
            try:
                self.go_to_account_space(contract)
            except (ServerError, BrowserUnavailable):
                return False
        return True

    @need_login
    def iter_spaces(self):
        if not self.total_spaces:
            # Determine how many spaces are present on the connection
            self.total_spaces = self.page.count_spaces()
            self.logger.info('The total number of spaces on this connection is %s.', self.total_spaces)
        for contract in range(self.total_spaces):
            # Switch to another space
            if not self.check_space_connection(contract):
                self.logger.warning(
                    'Server returned error 500 twice when trying to access space %s, this space will be skipped',
                    contract
                )
                continue
            yield contract

    @need_login
    def iter_accounts(self):
        self.location(self.accounts_url)
        if not self.accounts_page.is_here():
            # We have been logged out.
            self.do_login()
        # Complete accounts list is required to match card parent accounts
        # and to avoid accounts that are present on several spaces
        all_accounts = {}
        deferred_cards = {}

        for contract in self.iter_spaces():
            # Some spaces have no main account
            if self.page.has_main_account():
                # The main account is not located at the same place in the JSON.
                main_account = self.page.get_main_account()
                if main_account.balance == NotAvailable:
                    self.check_space_connection(contract)
                    main_account = self.page.get_main_account()
                    if main_account.balance == NotAvailable:
                        self.logger.warning('Could not fetch the balance for main account %s.', main_account.id)
                # Get cards for the main account
                if self.page.has_main_cards():
                    for card in self.page.iter_main_cards():
                        card.parent = main_account
                        card.currency = card.parent.currency
                        card.owner_type = card.parent.owner_type
                        card._category = card.parent._category
                        card._contract = contract
                        deferred_cards[card.id] = card

                main_account._contract = contract
            else:
                main_account = None

            space_type = self.page.get_space_type()
            accounts_list = list(self.page.iter_accounts())
            for account in accounts_list:
                account._contract = contract

            ''' Other accounts have no balance in the main JSON, so we must get all
            the (_id_element_contrat, balance) pairs in the account_details JSON.

            Account categories always correspond to the same account types:
            # Category 1: Checking accounts,
            # Category 2: To be determined,
            # Category 3: Savings,
            # Category 4: Loans & Credits,
            # Category 5: Insurances (skipped),
            # Category 6: To be determined,
            # Category 7: Market accounts. '''

            categories = {int(account._category) for account in accounts_list if account._category not in (None, '5')}
            account_balances = {}
            loan_ids = {}
            for category in categories:
                self.account_details.go(space=self.space, category=category)
                account_balances.update(self.page.get_account_balances())
                loan_ids.update(self.page.get_loan_ids())

            if main_account:
                if main_account.type == Account.TYPE_CHECKING:
                    main_account.iban = self.get_account_iban(main_account._index, 1, main_account.id)

                if main_account.id not in all_accounts:
                    all_accounts[main_account.id] = main_account
                    yield main_account

            for account in accounts_list:
                if empty(account.balance):
                    account.balance = account_balances.get(account._id_element_contrat, NotAvailable)

                if account.type == Account.TYPE_CHECKING:
                    account.iban = self.get_account_iban(account._index, account._category, account.id)

                # Loans have a specific ID that we need to fetch
                # so the backend can match loans properly.
                if account.type in (Account.TYPE_LOAN, Account.TYPE_CONSUMER_CREDIT):
                    account.id = account.number = loan_ids.get(account._id_element_contrat, account.id)
                    if empty(account.balance):
                        self.logger.warning(
                            'Loan skip: no balance is available for %s, %s account', account.id, account.label
                        )
                        continue
                    account = self.switch_account_to_loan(account)

                elif account.type == Account.TYPE_REVOLVING_CREDIT:
                    account.id = account.number = loan_ids.get(account._id_element_contrat, account.id)
                    account = self.switch_account_to_revolving(account)

                elif account.type == Account.TYPE_PER:
                    account = self.switch_account_to_per(account)

                if account.id not in all_accounts:
                    all_accounts[account.id] = account
                    yield account

            ''' Fetch all deferred credit cards for this space: from the space type
            we must determine the required URL parameters to build the cards URL.
            If there is no card on the space, the server will return a 500 error
            (it is the same on the website) so we must handle it with try/except. '''
            cards_parameters = {
                'PARTICULIER': ('particulier', 'moyens-paiement'),
                'HORS_MARCHE': ('particulier', 'moyens-paiement'),
                'PROFESSIONNEL': ('professionnel', 'paiements-encaissements'),
                'AGRICULTEUR': ('agriculteur', 'paiements-encaissements'),
                'ASSOC_CA_MODERE': ('association', 'paiements-encaissements'),
                'ENTREPRISE': ('entreprise', 'paiements-encaissements'),
                'PROFESSION_LIBERALE': ('professionnel', 'paiements-encaissements'),
                'PROMOTEURS': ('professionnel', 'paiements-encaissements'),
            }
            assert space_type in cards_parameters, 'Space type %s has never been encountered before.' % space_type

            space, op = cards_parameters[space_type]
            if 'banque-privee' in self.url:
                # The first parameter will always be 'banque-privee'.
                space = 'banque-privee'

            # The card request often fails, even on the website,
            # so we try twice just in case we fail to get there:
            for trial in range(2):
                try:
                    self.check_space_connection(contract)
                    self.cards.go(space=space, op=op)
                except (ServerError, ClientError, HTTPNotFound):
                    if trial == 0:
                        self.logger.warning('Request to cards failed, we try again.')
                    else:
                        self.logger.warning('Request to cards failed twice, the cards of this space will be skipped.')
                else:
                    break

            if self.cards.is_here():
                for card in self.page.iter_card_parents():
                    if card.id not in deferred_cards:
                        card.number = card.id
                        card.parent = all_accounts.get(card._parent_id, NotAvailable)
                        card.currency = card.parent.currency
                        card.owner_type = card.parent.owner_type
                        card._category = card.parent._category
                        card._contract = contract
                        deferred_cards[card.id] = card

        # We must check if cards are unique on their parent account;
        # if not, we cannot retrieve their summaries in iter_history.
        parent_accounts = []
        for card in deferred_cards.values():
            parent_accounts.append(card.parent.id)
        for card in deferred_cards.values():
            if parent_accounts.count(card.parent.id) == 1:
                card._unique = True
            else:
                card._unique = False
            yield card

    def switch_account_to_loan(self, account):
        loan = Loan()
        copy_attrs = (
            'id',
            'number',
            'label',
            'type',
            'currency',
            '_index',
            '_category',
            '_contract',
            '_id_element_contrat',
            'owner_type',
        )
        for attr in copy_attrs:
            setattr(loan, attr, getattr(account, attr))
        loan.balance = -account.balance
        return loan

    def switch_account_to_revolving(self, account):
        loan = Loan()
        copy_attrs = (
            'id',
            'number',
            'label',
            'type',
            'currency',
            '_index',
            '_category',
            '_contract',
            '_id_element_contrat',
            'owner_type',
        )
        for attr in copy_attrs:
            setattr(loan, attr, getattr(account, attr))
        loan.balance = Decimal(0)
        loan.available_amount = account.balance
        return loan

    def switch_account_to_per(self, account):
        per = Per.from_dict(account.to_dict())
        copy_attrs = (
            '_index',
            '_category',
            '_contract',
            '_id_element_contrat',
        )
        for attr in copy_attrs:
            setattr(per, attr, getattr(account, attr))

        if per.label == 'PER Assurance':
            per.provider_type = PerProviderType.INSURER
        else:
            per.provider_type = PerProviderType.BANK

        # No available information concerning PER version
        return per

    @need_login
    def go_to_account_space(self, contract):
        if self.total_spaces == 1:
            self.location(self.accounts_url)
            if not self.accounts_page.is_here():
                self.logger.warning('We have been loggged out, relogin.')
                self.do_login()
            return

        # This request often returns a 500 error on this quality website
        for tries in range(4):
            try:
                self.contracts_page.go(space=self.space, id_contract=contract)
            except ServerError as e:
                if e.response.status_code == 500:
                    self.logger.warning('Space switch returned a 500 error, try again.')
                    self.contracts_page.go(space=self.space, id_contract=contract)
                else:
                    raise
            if not self.accounts_page.is_here():
                self.logger.warning('We have been logged out, trying to relogin.')
                self.do_login()
            else:
                return
            if tries >= 3:
                raise BrowserUnavailable()

    @need_login
    def iter_history(self, account, coming=False):
        if account.type == Account.TYPE_CARD:
            card_transactions = []
            self.go_to_account_space(account._contract)
            # Deferred cards transactions have a specific JSON.
            # Only three months of history available for cards.
            value = int(not coming)
            params = {
                'grandeFamilleCode': int(account._category),
                'compteIdx': int(account.parent._index),
                'carteIdx': int(account._index),
                'rechercheEncoursDebite': value,
            }
            self.card_history.go(space=self.space, params=params)
            for tr in self.page.iter_card_history():
                card_transactions.append(tr)

            # If the card if not unique on the parent id, it is impossible
            # to know which summary corresponds to which card.
            if not coming and card_transactions and account._unique:
                # Get card summaries from parent account
                # until we reach the oldest card transaction
                last_transaction = card_transactions[-1]
                before_last_transaction = False
                params = {
                    'compteIdx': int(account.parent._index),
                    'grandeFamilleCode': int(account.parent._category),
                    'idDevise': str(account.parent.currency),
                    'idElementContrat': str(account.parent._id_element_contrat),
                }
                self.history.go(space=self.space, params=params)
                for tr in self.page.iter_history():
                    if tr.date < last_transaction.date:
                        before_last_transaction = True
                        break
                    if tr.type == Transaction.TYPE_CARD_SUMMARY:
                        tr.amount = -tr.amount
                        card_transactions.append(tr)

                while self.page.has_next_page() and not before_last_transaction:
                    next_index = self.page.get_next_index()
                    params = {
                        'grandeFamilleCode': int(account.parent._category),
                        'compteIdx': int(account.parent._index),
                        'idDevise': str(account.parent.currency),
                        'startIndex': next_index,
                        'count': 100,
                    }
                    self.history.go(space=self.space, params=params)
                    for tr in self.page.iter_history():
                        if tr.date < last_transaction.date:
                            before_last_transaction = True
                            break
                        if tr.type == Transaction.TYPE_CARD_SUMMARY:
                            tr.amount = -tr.amount
                            card_transactions.append(tr)

            for tr in sorted_transactions(card_transactions):
                yield tr
            return

        # These three parameters are required to get the transactions for non_card accounts
        if (
            empty(account._index) or empty(account._category) or empty(account._id_element_contrat)
            or account.type == Account.TYPE_CONSUMER_CREDIT
        ):
            return

        self.go_to_account_space(account._contract)
        params = {
            'compteIdx': int(account._index),
            'grandeFamilleCode': int(account._category),
            'idDevise': str(account.currency),
            'idElementContrat': str(account._id_element_contrat),
        }
        # This request might lead to occasional 500 errors
        for _ in range(2):
            try:
                self.history.go(space=self.space, params=params)
            except ServerError:
                self.logger.warning('Request to get account history failed.')
            else:
                break

        if not self.history.is_here():
            raise BrowserUnavailable()

        for tr in self.page.iter_history():
            # For "Livret A", value dates of transactions are always
            # 1st or 15th of the month so we specify a valuation date.
            # Example: rdate = 21/02, date=01/02 then vdate = 01/02.
            if account.type == Account.TYPE_SAVINGS:
                tr.vdate = tr.date
            yield tr

        # Get other transactions 100 by 100:
        while self.page.has_next_page():
            next_index = self.page.get_next_index()
            params = {
                'grandeFamilleCode': int(account._category),
                'compteIdx': int(account._index),
                'idDevise': str(account.currency),
                'startIndex': next_index,
                'count': 100,
            }
            self.history.go(space=self.space, params=params)
            for tr in self.page.iter_history():
                yield tr

    @need_login
    def iter_investment(self, account):
        if account.balance == 0 or empty(account.balance):
            return

        if (
            account.type == Account.TYPE_LIFE_INSURANCE
            and ('rothschild' in account.label.lower() or re.match(r'^open (perspective|strat)', account.label, re.I))
        ):
            # We must go to the right perimeter before trying to access the Life Insurance investments
            self.go_to_account_space(account._contract)
            self.life_insurance_investments.go(space=self.space, idx=account._index, category=account._category)
            if self.life_insurance_investments.is_here():
                for inv in self.page.iter_investments():
                    yield inv
            else:
                self.logger.warning('Failed to reach investment details for account %s', account.id)
            return

        elif (
            account.type in (Account.TYPE_LIFE_INSURANCE, Account.TYPE_CAPITALISATION)
            and re.search('vendome|aster sélection|espace gestion', account.label, re.I)
        ):
            # 'Vendome Optimum Euro', 'Vendome Patrimoine', 'Espace Gestion' & 'Aster sélection'
            # investments are on the BGPI space
            if self.bgpi_accounts.is_here() or self.bgpi_investments.is_here():
                # To avoid logouts by going from Cragr to Bgpi and back, we go directly to the account details.
                # When there are several BGPI accounts, this shortcut saves a lot of requests.
                self.bgpi_accounts.stay_or_go()
                account_url = self.page.get_account_url(account.id)
                if account_url:
                    self.location(account_url)
                    for inv in self.page.iter_investments():
                        yield inv
                    return

            self.go_to_account_space(account._contract)
            self.token_page.go()
            token = self.page.get_token()
            data = {
                'situation_travail': 'BGPI',
                ':cq_csrf_token': token,
            }
            self.bgpi_redirection.go(space=self.space, data=data)
            bgpi_url = self.page.get_bgpi_url()
            if not bgpi_url:
                self.logger.warning('Could not access BGPI space for account %s.', account.label)
                return

            self.location(bgpi_url)
            account.url = self.page.get_account_url(account.id)
            if not account.url:
                self.logger.warning('Account %s URL was not found on the BGPI space.', account.id)
                return

            self.location(account.url)
            for inv in self.page.iter_investments():
                yield inv

        elif account.type in (
            Account.TYPE_PER,
            Account.TYPE_PERP,
            Account.TYPE_PERCO,
            Account.TYPE_LIFE_INSURANCE,
            Account.TYPE_CAPITALISATION,
        ):
            if account.label == "Vers l'avenir":
                # Website crashes when clicking on these Life Insurances...
                return

            self.go_to_account_space(account._contract)
            self.token_page.go()
            token = self.page.get_token()
            data = {
                'situation_travail': 'CONTRAT',
                'idelco': account.id,
                ':cq_csrf_token': token,
            }
            try:
                self.predica_redirection.go(space=self.space, data=data)
                self.predica_investments.go()
            except ServerError:
                self.logger.warning('Got ServerError when fetching investments for account %s', account.id)
                return
            else:
                for inv in self.page.iter_investments():
                    yield inv

        elif account.type == Account.TYPE_PEA and account.label == 'Compte espèce PEA':
            yield create_french_liquidity(account.balance)
            return

        elif account.type in (Account.TYPE_PEA, Account.TYPE_MARKET):
            # Do not try to go to Netfinca if there is no money
            # on the account or the server will return an error 500
            if account.balance == 0:
                return
            self.go_to_account_space(account._contract)
            self.token_page.go()
            token = self.page.get_token()
            data = {
                'situation_travail': 'BANCAIRE',
                'num_compte': account.id,
                'code_fam_produit': account._fam_product_code,
                'code_fam_contrat_compte': account._fam_contract_code,
                ':cq_csrf_token': token,
            }

            # For some market accounts, investments are not even accessible,
            # and the only way to know if there are investments is to try
            # to go to the Netfinca space with the accounts parameters.
            try:
                self.netfinca_redirection.go(space=self.space, data=data)
            except BrowserHTTPNotFound:
                self.logger.info('Investments are not available for this account.')
                self.go_to_account_space(account._contract)
                return
            url = self.page.get_url()
            if 'netfinca' in url:
                self.location(url)
                self.netfinca.session.cookies.update(self.session.cookies)
                self.netfinca.accounts.go()
                self.netfinca.check_action_needed()
                for inv in self.netfinca.iter_investments(account):
                    if inv.code == 'XX-liquidity' and account.type == Account.TYPE_PEA:
                        # Liquidities are already fetched on the "PEA espèces"
                        continue
                    yield inv

    @need_login
    def iter_market_orders(self, account):
        if (
            account.type not in (Account.TYPE_MARKET, Account.TYPE_PEA)
            or account.label == 'Compte espèce PEA'
            or account.balance == 0
        ):
            # Do not try to go to Netfinca if there is no money on the
            # account otherwise the server will return a 500 error
            return

        if (
            self.netfinca.accounts.is_here()
            or self.netfinca.investments.is_here()
            or self.netfinca.market_orders.is_here()
        ):
            # Avoid going back to Cragr to go back to Netfinca if already on Netfinca.
            # This avoids unnecessary logouts and saves a lot of requests, but only
            # works if the accounts are on the same perimeter.
            self.netfinca.accounts.go()
            self.netfinca.check_action_needed()
            if self.netfinca.is_account_present(account.id):
                for order in self.netfinca.iter_market_orders(account):
                    yield order
                return
            # If we did not pass in the 'if' statement right above, it means we are
            # not on the right Netfinca perimeter, so we proceed with the code below:
            # go back to Cragr website and go to the correct Netfinca perimeter.

        self.go_to_account_space(account._contract)
        token = self.token_page.go().get_token()
        data = {
            'situation_travail': 'BANCAIRE',
            'num_compte': account.id,
            'code_fam_produit': account._fam_product_code,
            'code_fam_contrat_compte': account._fam_contract_code,
            ':cq_csrf_token': token,
        }
        # For some accounts the Netfinca space is not accessible,
        # the only way to know if there are investments is to try
        # to go to the Netfinca space with the account parameters.
        try:
            self.netfinca_redirection.go(space=self.space, data=data)
        except BrowserHTTPNotFound:
            self.logger.info('Market orders are not available for this account.')
            self.go_to_account_space(account._contract)
            return

        url = self.page.get_url()
        if 'netfinca' in url:
            self.location(url)
            self.netfinca.session.cookies.update(self.session.cookies)
            self.netfinca.accounts.go()
            for order in self.netfinca.iter_market_orders(account):
                yield order

    @need_login
    def iter_advisor(self):
        self.go_to_account_space(0)
        owner_type = self.page.get_owner_type()
        self.profile_page.go(space=self.space)
        if owner_type == 'PRIV':
            advisor = self.page.get_advisor()
            self.profile_details.go(space=self.space)
            self.page.fill_advisor(obj=advisor)
            yield advisor
        elif owner_type == 'ORGA':
            advisor = self.page.get_advisor()
            self.pro_profile_details.go(space=self.space)
            self.page.fill_advisor(obj=advisor)
            yield advisor

    @need_login
    def get_profile(self):
        # There is one profile per space, so we only fetch the first one
        self.go_to_account_space(0)
        owner_type = self.page.get_owner_type()
        self.profile_page.go(space=self.space)
        if owner_type == 'PRIV':
            profile = self.page.get_user_profile()
            self.profile_details.go(space=self.space)
            self.page.fill_profile(obj=profile)
            return profile
        elif owner_type == 'ORGA':
            profile = self.page.get_company_profile()
            self.pro_profile_details.go(space=self.space)
            self.page.fill_profile(obj=profile)
            return profile

    def get_space_info(self):
        operations = {
            'particulier': 'moyens-paiement',
            'professionnel': 'paiements-encaissements',
            'association': 'paiements-encaissements',
            'entreprise': 'paiements-encaissements',
            'banque-privee': 'moyens-paiement',
            'agriculteur': 'paiements-encaissements',
            'promoteurs': 'paiements-encaissements',
        }

        referer = self.absurl('/%s/operations/%s/virement.html.html' % (self.space, operations[self.space]))

        return operations[self.space], referer

    @need_login
    def get_account_transfer_space_info(self, account):
        self.go_to_account_space(account._contract)

        connection_id = self.page.get_connection_id()
        operation, referer = self.get_space_info()

        return self.space, operation, referer, connection_id

    @need_login
    def iter_debit_accounts(self):
        assert self.recipients.is_here()
        for index, debit_accounts in enumerate(self.page.iter_debit_accounts()):
            debit_accounts._index = index
            if self.page.is_sender_account(debit_accounts.id):
                # only yield able to do transfer accounts
                yield debit_accounts

    @need_login
    def iter_transfer_recipients(self, account, transfer_space_info=None):
        if account.type in (
            account.TYPE_CARD,
            account.TYPE_LOAN,
            account.TYPE_LIFE_INSURANCE,
            account.TYPE_PEA,
            account.TYPE_CONSUMER_CREDIT,
            account.TYPE_REVOLVING_CREDIT,
        ):
            return

        # avoid to call `get_account_transfer_space_info()` several times
        if transfer_space_info:
            space, operation, referer = transfer_space_info
        else:
            space, operation, referer, _ = self.get_account_transfer_space_info(account)

        self.go_to_account_space(account._contract)
        self.recipients.go(space=space, op=operation, headers={'Referer': referer})

        if not self.page.is_sender_account(account.id):
            return

        # can't use 'ignore_duplicate' in DictElement because we need the 'index' to do transfer
        seen = set()
        seen.add(account.id)

        for index, internal_rcpt in enumerate(self.page.iter_internal_recipient()):
            internal_rcpt._index = index
            if internal_rcpt._is_recipient and (internal_rcpt.id not in seen):
                seen.add(internal_rcpt.id)
                yield internal_rcpt

        for index, external_rcpt in enumerate(self.page.iter_external_recipient()):
            external_rcpt._index = index
            if external_rcpt.id not in seen:
                seen.add(external_rcpt.id)
                yield external_rcpt

    @need_login
    def init_transfer(self, transfer, **params):
        # first, get _account on account list to get recipient
        _account = strict_find_object(self.iter_accounts(), id=transfer.account_id, error=AccountNotFound)

        # get information to go on transfer page
        space, operation, referer, connection_id = self.get_account_transfer_space_info(account=_account)

        recipient = strict_find_object(
            self.iter_transfer_recipients(_account, transfer_space_info=(space, operation, referer)),
            id=transfer.recipient_id,
            error=RecipientNotFound
        )
        # Then, get account on transfer account list to get index and other information
        account = strict_find_object(self.iter_debit_accounts(), id=_account.id, error=AccountNotFound)

        # get token and transfer token to init transfer
        token = self.token_page.go().get_token()
        transfer_token = self.transfer_token.go(space=space, op=operation, headers={'Referer': referer}).get_token()

        if transfer.label:
            label = transfer.label[:33].encode('ISO-8859-15', errors='ignore').decode('ISO-8859-15')
            transfer.label = re.sub(r'[+!]', '', label)

        data = {
            'connexionId': connection_id,
            'cr': self.session.cookies['caisse-regionale'],
            'creditAccountIban': recipient.iban,
            'creditAccountIndex': recipient._index,
            'debitAccountIndex': account._index,
            'debitAccountNumber': account.number,
            'externalAccount': recipient.category == 'Externe',
            'recipientName': recipient.label,
            'transferAmount': transfer.amount,
            'transferComplementaryInformation1': transfer.label,
            'transferComplementaryInformation2': '',
            'transferComplementaryInformation3': '',
            'transferComplementaryInformation4': '',
            'transferCurrencyCode': account.currency,
            'transferDate': transfer.exec_date.strftime('%d/%m/%Y'),
            'transferFrequency': 'U',
            'transferRef': transfer.label,
            'transferType': 'UNIQUE',
            'typeCompte': account.label,
        }

        # update transfer data according to recipient category
        if recipient.category == 'Interne':
            data['creditAccountNumber'] = recipient.id
            data['recipientName'] = recipient._owner_name

        # init transfer request
        self.transfer.go(
            space=space,
            op=operation,
            headers={
                'Referer': referer,
                'CSRF-Token': token,
                'NPC-Generated-Token': transfer_token,
            },
            json=data
        )
        assert self.page.check_transfer()
        # get recap because it's not returned by init transfer request
        self.transfer_recap.go(
            space=space,
            op=operation,
            headers={'Referer': self.absurl('/%s/operations/%s/virement.postredirect.html' % (space, operation))}
        )
        # information needed to exec transfer
        transfer._space = space
        transfer._operation = operation
        transfer._token = token
        transfer._connection_id = connection_id
        return self.page.handle_response(transfer)

    @need_login
    def execute_transfer(self, transfer, **params):
        self.transfer_exec.go(
            space=transfer._space,
            op=transfer._operation,
            headers={
                'Referer': self.absurl(
                    '/%s/operations/%s/virement.postredirect.html' % (transfer._space, transfer._operation)
                ),
                'CSRF-Token': transfer._token,
            },
            json={'connexionId': transfer._connection_id}
        )
        assert self.page.check_transfer_exec()
        return transfer

    def continue_sms_recipient(self, recipient, otp_sms):
        # We need those 2 to validate the otp
        assert self.transaction_id, 'Need a transaction_id to continue adding a recipient by sms'
        assert self.sms_csrf_token, 'Need a sms_csrf_token to continue adding a recipient by sms'

        if len(otp_sms) != 6 or not re.match(r'(?:[0-9]*[A-Z][0-9]*)\Z', otp_sms):
            # When the code does not match the regex, a generic error
            # message is sent by the website, so we need to manually handle
            # it to avoid catching other errors in the `except` below.
            raise RecipientInvalidOTP('Code SMS invalide.')

        try:
            self.validate_sms.go(
                space=self.space,
                headers={
                    'CSRF-Token': self.sms_csrf_token,
                    'Referer': self.new_recipient_sms.build(
                        space=self.space,
                        transaction_id=self.transaction_id,
                    ),
                },
                data={
                    'codeVirtuel': otp_sms,
                    'transactionId': self.transaction_id,
                },
            )
        except ServerError as e:
            if e.response.status_code == 500:
                message = e.response.json()['message']
                if 'Le code saisi est incorrect' in message:
                    raise RecipientInvalidOTP(message)
            raise

        # We don't need to do anything here, beside going
        # on this page for the following requests to work.
        self.check_sms.go(space=self.space, transaction_id=self.transaction_id)

        # We need those 2 differents tokens to verify the recipient.
        self.recipient_token.go(
            space=self.space,
            transaction_id=self.transaction_id,
        )
        recipient_token = self.page.get_token()

        self.token_page.go()
        token = self.page.get_token()

        self.verify_new_recipient.go(
            space=self.space,
            transaction_id=self.transaction_id,
            headers={
                'CSRF-Token': token,
                'NPC-Generated-Token': recipient_token,
            },
            data={
                'iban_code': recipient.iban,
                'recipient_name': recipient.label,
            },
        )

        self.add_new_recipient.go(
            space=self.space,
            params={'transactionId': self.transaction_id},
        )

        error = self.page.get_error()
        if error:
            raise RecipientInvalidIban(message=error)

        self.token_page.go()
        token = self.page.get_token()

        self.validate_new_recipient.go(
            space=self.space,
            transaction_id=self.transaction_id,
            method='POST',
            headers={'CSRF-Token': token},
        )

        # The redirect URL is a relative url, we either
        # land on add_new_recipient or end_new_recipient
        url = '../' + self.page.get_redirect_url()
        url = urljoin(self.url, url)
        self.location(url)

        error = self.page.get_error()
        if error:
            raise AddRecipientBankError(message=error)

        message = self.page.get_validated_message()
        if 'un délai de quelques jours peut être nécessaire' in message:
            # Full message is :
            # Pour garantir votre sécurité, un délai de quelques jours peut être
            # nécessaire avant que cet ajout soit validé
            recipient.enabled_at = datetime.now().replace(microsecond=0) + timedelta(days=3)

        return recipient

    @need_login
    def init_new_recipient(self, recipient, **params):
        recipient.id = recipient.iban
        recipient.enabled_at = datetime.now().replace(microsecond=0)
        recipient.currency = 'EUR'
        recipient.bank_name = NotAvailable
        # Remove characters that are not supported by the website.
        recipient.label = re.sub(r'[^0-9a-zA-Z /?:.,"()-]', '', recipient.label)
        recipient.label = re.sub(r'\s+', ' ', recipient.label).strip()

        # This url redirects us on a page asking for an sms code (/sms.otp.html)
        # or an app validation (/securipass.securipass.html).
        url = self.add_new_recipient.build(space=self.space)

        try:
            self.location(url, allow_redirects=False)
        except BrowserHTTPNotFound:
            # User cannot add external recipients
            raise AddRecipientBankError(message="Impossible d'ajouter un bénéficiaire externe")

        if 'sms.otp' not in self.response.headers['Location']:
            raise AuthMethodNotImplemented()

        self.location(self.response.headers['Location'])

        # Even if we already validated the sms for the current session,
        # we still need to validate one each time we want to add a new
        # recipient.
        assert self.new_recipient_sms.is_here(), 'Landed on the wrong page'

        url_params = parse_qs(urlparse(self.url).query)
        self.transaction_id = url_params['transactionId'][0]

        self.token_page.go()
        self.sms_csrf_token = self.page.get_token()

        # This send a sms
        self.send_sms.go(
            space=self.space,
            headers={
                'CSRF-Token': self.sms_csrf_token,
                'Referer': self.new_recipient_sms.build(
                    space=self.space,
                    transaction_id=self.transaction_id,
                ),
            },
            data={'transactionId': self.transaction_id},
        )

        self.need_reload_state = True

        raise AddRecipientStep(
            recipient,
            Value(
                'otp_sms',
                label='Veuillez saisir le code reçu par SMS',
            ),
        )

    def new_recipient(self, recipient, **params):
        if 'otp_sms' in params:
            return self.continue_sms_recipient(recipient, params['otp_sms'])

        return self.init_new_recipient(recipient, **params)

    @need_login
    def iter_emitters(self):
        """
        Get the emitters from each space
        """
        self.location(self.accounts_url)
        if not self.accounts_page.is_here():
            # We have been logged out.
            self.do_login()
        for _ in self.iter_spaces():
            operation, referer = self.get_space_info()
            self.recipients.go(space=self.space, op=operation, headers={'Referer': referer})
            for emitter in self.page.iter_emitters():
                yield emitter
