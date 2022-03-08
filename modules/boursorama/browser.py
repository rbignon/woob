# -*- coding: utf-8 -*-

# Copyright(C) 2016       Baptiste Delpey
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

from __future__ import unicode_literals

import re
from datetime import date, datetime
from urllib.parse import urlsplit

import requests
from dateutil.relativedelta import relativedelta

from woob.browser.retry import login_method, retry_on_logout, RetryLoginBrowser
from woob.browser.browsers import need_login, TwoFactorBrowser
from woob.browser.url import URL
from woob.exceptions import (
    BrowserIncorrectPassword, BrowserHTTPNotFound, NoAccountsException,
    BrowserUnavailable, ActionNeeded, BrowserQuestion,
    AuthMethodNotImplemented, BrowserUserBanned,
)
from woob.browser.exceptions import LoggedOut, ClientError, ServerError
from woob.capabilities.bank import (
    Account, AccountNotFound, TransferError, TransferInvalidAmount,
    TransferInvalidEmitter, TransferInvalidLabel, TransferInvalidRecipient,
    AddRecipientStep, Rate, TransferBankError, AccountOwnership, RecipientNotFound,
    AddRecipientTimeout, TransferDateType, Emitter, TransactionType,
    AddRecipientBankError, TransferStep, TransferTimeout,
    AccountOwnerType,
)
from woob.capabilities.base import (
    find_object, strict_find_object,
    empty, NotLoaded, NotAvailable,
)
from woob.capabilities.contact import Advisor
from woob.tools.value import Value
from woob.tools.capabilities.bank.transactions import sorted_transactions
from woob.tools.capabilities.bank.bank_transfer import sorted_transfers

from .pages import (
    VirtKeyboardPage, AccountsPage, AsvPage, HistoryPage, AuthenticationPage,
    MarketPage, LoanPage, SavingMarketPage, ErrorPage, IncidentPage, IbanPage, ProfilePage, ExpertPage,
    CardInformationPage, CalendarPage, HomePage, PEPPage,
    TransferAccounts, TransferRecipients, TransferCharacteristics, TransferConfirm, TransferSent,
    AddRecipientPage, StatusPage, CardHistoryPage, CardCalendarPage, CurrencyListPage, CurrencyConvertPage,
    AccountsErrorPage, NoAccountPage, TransferMainPage, PasswordPage, NewTransferWizard,
    NewTransferEstimateFees, NewTransferUnexpectedStep, NewTransferConfirm, NewTransferSent, CardSumDetailPage,
    MinorPage, AddRecipientOtpSendPage, OtpPage, OtpCheckPage, PerPage,
)
from .transfer_pages import TransferListPage, TransferInfoPage
from .document_pages import (
    BankIdentityPage, BankStatementsPage, PdfDocumentPage,
)

__all__ = ['BoursoramaBrowser']


class BoursoramaBrowser(RetryLoginBrowser, TwoFactorBrowser):
    BASEURL = 'https://clients.boursorama.com'
    TIMEOUT = 60.0
    HAS_CREDENTIALS_ONLY = True
    TWOFA_DURATION = 60 * 24 * 90

    home = URL('/$', HomePage)
    keyboard = URL(r'/connexion/clavier-virtuel\?_hinclude=1', VirtKeyboardPage)
    # following URL has to be declared early because there are two other URL with the same url
    # PdfDocumentPage has been declared with a is_here attribute to be differentiated to the 2 others
    # (the two other pages seem to be in csv format)
    pdf_document_page = URL(r'https://api.boursorama.com/services/api/files/download.phtml.*', PdfDocumentPage)
    status = URL(r'/aide/messages/dashboard\?showza=0&_hinclude=1', StatusPage)
    calendar = URL('/compte/cav/.*/calendrier', CalendarPage)
    card_calendar = URL('https://api.boursorama.com/services/api/files/download.phtml.*', CardCalendarPage)
    error = URL(
        '/connexion/compte-verrouille',
        '/infos-profil',
        ErrorPage
    )
    login = URL(
        r'/connexion/saisie-mot-de-passe',
        # When getting logged out, we get redirected to
        # either /connexion/ or /connexion/?ubiquite=1 or /connexion/?ubiquite= or /connexion/?org=...
        r'/connexion/$',
        r'/connexion/(\?ubiquite=1?)?$',
        r'/connexion/(\?org=.*)?$',
        r'/connexion/\?expire=$',
        PasswordPage
    )
    otp_send = URL(
        r'https://api.boursorama.com/services/api/v1.7/_user_/_(?P<user_hash>.*)_/session/otp/startsms/(?P<otp_number>.*)',
        OtpPage
    )
    otp_validation = URL(
        r'https://api.boursorama.com/services/api/v1.7/_user_/_(?P<user_hash>.*)_/session/otp/checksms/(?P<otp_number>.*)',
        OtpCheckPage
    )
    minor = URL(r'/connexion/mineur', MinorPage)
    accounts = URL(r'/dashboard/comptes\?_hinclude=300000', AccountsPage)
    accounts_error = URL(r'/dashboard/comptes\?_hinclude=300000', AccountsErrorPage)
    pro_accounts = URL(r'/dashboard/comptes-professionnels\?_hinclude=1', AccountsPage)
    no_account = URL(
        r'/dashboard/comptes\?_hinclude=300000',
        r'/dashboard/comptes-professionnels\?_hinclude=1',
        NoAccountPage
    )

    history = URL(r'/compte/(cav|epargne)/(?P<webid>.*)/mouvements.*', HistoryPage)
    card_transactions = URL('/compte/cav/(?P<webid>.*)/carte/.*', HistoryPage)
    deffered_card_history = URL('https://api.boursorama.com/services/api/files/download.phtml.*', CardHistoryPage)
    budget_transactions = URL('/budget/compte/(?P<webid>.*)/mouvements.*', HistoryPage)
    other_transactions = URL('/compte/cav/(?P<webid>.*)/mouvements.*', HistoryPage)
    saving_transactions = URL('/compte/epargne/csl/(?P<webid>.*)/mouvements.*', HistoryPage)
    card_summary_detail_transactions = URL(r'/contre-valeurs-operation/.*', CardSumDetailPage)
    saving_pep = URL('/compte/epargne/pep', PEPPage)
    incident = URL('/compte/cav/(?P<webid>.*)/mes-incidents.*', IncidentPage)

    # transfer
    transfer_list = URL(
        r'/compte/(?P<acc_type>[^/]+)/(?P<webid>\w+)/virements/suivi/(?P<type>\w+)$',
        # next url is for pagination, token is very long
        # make sure you don't match "details" or it could break "transfer_info" URL
        r'/compte/(?P<acc_type>[^/]+)/(?P<webid>\w+)/virements/suivi/(?P<type>\w+)/[a-zA-Z0-9]{30,}$',
        TransferListPage
    )
    transfer_info = URL(
        r'/compte/(?P<acc_type>[^/]+)/(?P<webid>\w+)/virements/suivi/(?P<type>\w+)/details/[\w-]{40,}',
        TransferInfoPage
    )
    transfer_main_page = URL(r'/compte/(?P<acc_type>[^/]+)/(?P<webid>\w+)/virements$', TransferMainPage)
    transfer_accounts = URL(
        r'/compte/(?P<acc_type>[^/]+)/(?P<webid>\w+)/virements/nouveau$',
        r'/compte/(?P<type>[^/]+)/(?P<webid>\w+)/virements/nouveau/(?P<id>\w+)/1',
        TransferAccounts
    )
    recipients_page = URL(
        r'/compte/(?P<type>[^/]+)/(?P<webid>\w+)/virements$',
        r'/compte/(?P<type>[^/]+)/(?P<webid>\w+)/virements/nouveau/(?P<id>\w+)/2',
        TransferRecipients
    )
    transfer_characteristics = URL(
        r'/compte/(?P<type>[^/]+)/(?P<webid>\w+)/virements/nouveau/(?P<id>\w+)/3',
        TransferCharacteristics
    )
    transfer_confirm = URL(
        r'/compte/(?P<type>[^/]+)/(?P<webid>\w+)/virements/nouveau/(?P<id>\w+)/4',
        TransferConfirm
    )
    transfer_sent = URL(
        r'/compte/(?P<type>[^/]+)/(?P<webid>\w+)/virements/nouveau/(?P<id>\w+)/5',
        TransferSent
    )
    # transfer_type should be one of : "immediat", "programme"
    new_transfer_wizard = URL(
        r'/compte/(?P<acc_type>[^/]+)/(?P<webid>\w+)/virements/(?P<transfer_type>immediat|programme)/nouveau/?$',
        r'/compte/(?P<acc_type>[^/]+)/(?P<webid>\w+)/virements/immediat/nouveau/(?P<id>\w+)/(?P<step>[1-6])$',
        r'/compte/(?P<acc_type>[^/]+)/(?P<webid>\w+)/virements/programme/nouveau/(?P<id>\w+)/(?P<step>[1-7])$',
        NewTransferWizard
    )
    new_transfer_estimate_fees = URL(
        r'/compte/(?P<acc_type>[^/]+)/(?P<webid>\w+)/virements/immediat/nouveau/(?P<id>\w+)/7$',
        r'/compte/(?P<acc_type>[^/]+)/(?P<webid>\w+)/virements/programme/nouveau/(?P<id>\w+)/8$',
        NewTransferEstimateFees
    )
    new_transfer_confirm = URL(
        r'/compte/(?P<acc_type>[^/]+)/(?P<webid>\w+)/virements/immediat/nouveau/(?P<id>\w+)/[78]$',
        r'/compte/(?P<acc_type>[^/]+)/(?P<webid>\w+)/virements/programme/nouveau/(?P<id>\w+)/[89]$',
        NewTransferConfirm
    )
    new_transfer_unexpected_step = URL(
        r'/compte/(?P<acc_type>[^/]+)/(?P<webid>\w+)/virements/immediat/nouveau/(?P<id>\w+)/7$',
        r'/compte/(?P<acc_type>[^/]+)/(?P<webid>\w+)/virements/programme/nouveau/(?P<id>\w+)/8$',
        NewTransferUnexpectedStep
    )
    new_transfer_sent = URL(
        r'/compte/(?P<acc_type>[^/]+)/(?P<webid>\w+)/virements/immediat/nouveau/(?P<id>\w+)/9$',
        r'/compte/(?P<acc_type>[^/]+)/(?P<webid>\w+)/virements/programme/nouveau/(?P<id>\w+)/10$',
        NewTransferSent
    )
    rcpt_page = URL(
        r'/compte/(?P<type>[^/]+)/(?P<webid>\w+)/virements/comptes-externes/nouveau/(?P<id>\w+)/\d',
        AddRecipientPage
    )
    rcpt_send_otp_page = URL(
        r'https://api.boursorama.com/services/api/v\d+\.\d+/_user_/_\w+_/session/otp/start(?P<otp_type>\w+)/\d+',
        AddRecipientOtpSendPage,
    )
    rcpt_check_otp_page = URL(
        r'https://api.boursorama.com/services/api/v\d+\.\d+/_user_/_\w+_/session/otp/check(?P<otp_type>\w+)/\d+',
        OtpCheckPage,
    )

    asv = URL('/compte/assurance-vie/.*', AsvPage)
    per = URL('/compte/per/.*', PerPage)
    saving_history = URL(
        '/compte/cefp/.*/(positions|mouvements)',
        '/compte/.*ord/.*/mouvements',
        '/compte/pea/.*/mouvements',
        '/compte/0%25pea/.*/mouvements',
        '/compte/pea-pme/.*/mouvements',
        SavingMarketPage
    )
    market = URL(
        r'/compte/(?!assurance|cav|epargne).*/(positions|mouvements|ordres)',
        r'/compte/ord/.*/positions',
        MarketPage
    )
    loans = URL(
        r'/credit/paiement-3x/.*/informations',
        r'/credit/immobilier/.*/informations',
        r'/credit/immobilier/.*/caracteristiques',
        r'/credit/consommation/.*/informations',
        r'/credit/lombard/.*/caracteristiques',
        LoanPage
    )
    authentication = URL('/securisation', AuthenticationPage)
    iban = URL('/compte/(?P<webid>.*)/rib', IbanPage)
    profile = URL('/mon-profil/', ProfilePage)
    profile_children = URL('/mon-profil/coordonnees/enfants', ProfilePage)

    expert = URL('/compte/derive/', ExpertPage)

    card_information = URL('/compte/cav/cb/informations/(?P<webid>.*)/(?P<key>.*)', CardInformationPage)

    currencylist = URL('https://www.boursorama.com/bourse/devises/parite/_detail-parite', CurrencyListPage)
    currencyconvert = URL(
        'https://www.boursorama.com/bourse/devises/convertisseur-devises/convertir',
        CurrencyConvertPage
    )

    statements_page = URL(r'/documents/releves', BankStatementsPage)
    rib_page = URL(r'/documents/compte-bancaire', BankIdentityPage)

    __states__ = ('recipient_form', 'transfer_form', 'user_hash', 'otp_number', 'otp_token',)

    def __init__(self, config=None, *args, **kwargs):
        self.config = config
        self.otp_number = None
        self.user_hash = None
        self.otp_token = None
        self.cards_list = None
        self.deferred_card_calendar = None
        self.recipient_form = None
        self.transfer_form = None
        kwargs['username'] = self.config['login'].get()
        kwargs['password'] = self.config['password'].get()

        self.AUTHENTICATION_METHODS = {
            'code': self.handle_sms,
        }

        super(BoursoramaBrowser, self).__init__(config, *args, **kwargs)

    def locate_browser(self, state):
        try:
            self.location(state['url'])
        except (requests.exceptions.HTTPError, requests.exceptions.TooManyRedirects, LoggedOut):
            pass

    def load_state(self, state):
        # needed to continue the session while adding recipient with otp or 2FA validation
        # it keeps the form to continue to submit the otp
        if state.get('recipient_form') or state.get('transfer_form') or state.get('otp_number'):
            state.pop('url', None)

        super(BoursoramaBrowser, self).load_state(state)

    def handle_authentication(self):
        if self.authentication.is_here():
            confirmation_link = self.page.get_confirmation_link()
            if confirmation_link:
                self.location(confirmation_link)

            if self.page.has_skippable_2fa():
                # The 2FA can be done before the end of the 90d
                # We skip it
                return

            self.check_interactive()

            api_config = self.page.get_api_config()
            self.otp_token = 'Bearer %s' % api_config['DEFAULT_API_BEARER']
            headers = {
                'Authorization': self.otp_token,
                'x-referer-feature-id': '_._.sca',
            }
            self.user_hash = api_config['USER_HASH']
            self.otp_number = self.page.get_otp_number()
            self.otp_send.go(
                user_hash=self.user_hash, otp_number=self.otp_number,
                headers=headers, json={},
            )

            raise BrowserQuestion(Value('code', label='Entrez le code reçu par SMS'))

    def handle_sms(self):
        headers = {
            'Authorization': self.otp_token,
            'x-referer-feature-id': '_._.sca',
        }
        try:
            self.otp_validation.go(
                user_hash=self.user_hash, otp_number=self.otp_number,
                headers=headers, json={'token': self.code}
            )
        except ServerError as e:
            error = e.response.json().get('error', '')
            if error:
                error_message = error.get('message')
                if error_message == "Le code d'authentification est incorrect":
                    raise BrowserIncorrectPassword(error_message)

                raise AssertionError('otp validation error: %s' % error_message)

            raise

        self.otp_number = self.user_hash = self.otp_token = None
        self.status.go()
        # The request does multiple redirect to go on home page
        # after that we are really logged

    def init_login(self):
        self.login.go()
        self.page.enter_password(self.username, self.password)

        if self.minor.is_here():
            error_message = self.page.get_error_message()
            # The full message here is "Votre dossier de passage à la majorité est validé ! Vous pourrez vous connecter à votre Espace Client dès votre majorité."
            if 'Votre dossier de passage à la majorité est validé' in error_message:
                raise BrowserUnavailable(error_message)
            # Here we raise an ActionNeeded because in this case the users will have 18 yo soon, and he have to update his informations
            # The message is hardcoded because the error_message in this case is really big and not really relevant.
            if 'nous devons collecter quelques éléments vous concernant.' in error_message:
                raise ActionNeeded('Vous avez 18 ans, veuillez mettre à jour votre dossier.')
            if 'pas accessible aux jeunes de moins de 18 ans.' in error_message:
                raise BrowserUserBanned(self.page.get_error_message())
            # The full message here is " Vous pourrez accéder à vos comptes dans quelques minutes, pour cela, il vous suffit de finaliser la mise à jour de votre
            # dossier. Il vous reste à : Ensuite vous aurez accès à vos comptes et pourrez commander une Carte Bancaire : Si vous êtes détenteur de l'offre Freedom,
            # votre CB sera utilisable jusqu'à vos 18 ans et 2 mois, il sera donc important que vous commandiez une nouvelle carte en ligne pour continuer à profiter
            # d'un moyen de paiement chez Boursorama Banque"
            if 'finaliser la mise à jour de votre dossier' in error_message:
                raise ActionNeeded('Une mise à jour de votre dossier est nécessaire pour accéder à votre espace banque en ligne.')
            if 'impératif que vous les complétiez dès à présent.' in error_message:
                raise ActionNeeded(error_message)
            raise AssertionError('Unhandled error message: %s' % error_message)
        elif self.error.is_here():
            error_message = self.page.get_error_message()
            if 'verrouille' in error_message:
                raise ActionNeeded(error_message)
            raise AssertionError('Unhandled error message : "%s"' % error_message)
        elif self.login.is_here():
            error = self.page.get_error()
            assert error, 'Should not be on login page without error message'

            is_wrongpass = re.search(
                "Identifiant ou mot de passe invalide"
                + "|Erreur d'authentification"
                + "|Cette valeur n'est pas valide"
                + "|votre identifiant ou votre mot de passe n'est pas valide",
                error
            )

            is_website_unavailable = re.search(
                "vous pouvez actuellement rencontrer des difficultés pour accéder à votre Espace Client"
                + "|Une erreur est survenue. Veuillez réessayer ultérieurement"
                + "|Maintenance en cours, merci de réessayer ultérieurement."
                + "|Oups, Il semble qu'une erreur soit survenue de notre côté"
                + "|Service momentanément indisponible",
                error
            )

            if is_website_unavailable:
                raise BrowserUnavailable()
            elif is_wrongpass:
                raise BrowserIncorrectPassword(error)
            elif "pour changer votre mot de passe" in error:
                # this popup appears after few wrongpass errors and requires a password change
                raise ActionNeeded(error)

            raise AssertionError('Unhandled error message : "%s"' % error)

        # After login, we might be redirected to the two factor authentication page.
        self.handle_authentication()

    @login_method
    def do_login(self):
        return super(BoursoramaBrowser, self).do_login()

    def ownership_guesser(self, accounts_list):
        ownerless_accounts = [account for account in accounts_list if empty(account.ownership)]

        if ownerless_accounts:
            # On Boursorama website, all mandatory accounts have the real owner name in their label, and
            # children names are findable in the PSU profile.
            self.profile_children.go()
            children_names = self.page.get_children_firstnames()

            for ownerless_account in ownerless_accounts:
                for child_name in children_names:
                    if child_name in ownerless_account.label:
                        ownerless_account.ownership = AccountOwnership.ATTORNEY
                        break

        # If there are two deferred card for with the same parent account, we assume that's the parent checking
        # account is a 'CO_OWNER' account
        parent_accounts = []
        for account in accounts_list:
            if account.type == Account.TYPE_CARD and empty(account.parent.ownership):
                if account.parent in parent_accounts:
                    account.parent.ownership = AccountOwnership.CO_OWNER
                parent_accounts.append(account.parent)

        # We set all accounts without ownership as if they belong to the credential owner
        for account in accounts_list:
            if empty(account.ownership) and account.type != Account.TYPE_CARD:
                account.ownership = AccountOwnership.OWNER

        # Account cards should be set with the same ownership of their parents accounts
        for account in accounts_list:
            if account.type == Account.TYPE_CARD:
                account.ownership = account.parent.ownership

    @retry_on_logout()
    @need_login
    def get_accounts_list(self):
        self.status.go()

        accounts_list = None  # necessary to loop again after being logged out

        exc = None
        for _ in range(3):
            if accounts_list is not None:
                break

            accounts_list = []
            loans_list = []
            # Check that there is at least one account for this user
            has_account = False
            self.pro_accounts.go()
            if self.pro_accounts.is_here():
                accounts_list.extend(self.get_filled_accounts(pro=True))
                has_account = True
            else:
                # We dont want to let has_account=False if we landed on an unknown page
                # it has to be the no_accounts page
                assert self.no_account.is_here()

            try:
                self.accounts.go()
            except BrowserUnavailable as e:
                self.logger.warning('par accounts seem unavailable, retrying')
                exc = e
                accounts_list = None
                continue
            else:
                if self.accounts.is_here():
                    accounts_list.extend(self.get_filled_accounts())
                    has_account = True
                else:
                    # We dont want to let has_account=False if we landed on an unknown page
                    # it has to be the no_accounts page
                    assert self.no_account.is_here()

                exc = None

            if not has_account:
                # if we landed twice on NoAccountPage, it means there is neither pro accounts nor pp accounts
                raise NoAccountsException()

            for account in list(accounts_list):
                if account.type == Account.TYPE_LOAN:
                    # Loans details are present on another page so we create
                    # a Loan object and remove the corresponding Account:
                    self.location(account.url)
                    loan = self.page.get_loan()
                    loan.url = account.url
                    loans_list.append(loan)
                    accounts_list.remove(account)
            accounts_list.extend(loans_list)

            self.cards_list = [acc for acc in accounts_list if acc.type == Account.TYPE_CARD]
            for card in self.cards_list:
                self.card_information.go(webid=card._webid, key=card._key)

                if not self.card_information.is_here():
                    self.logger.warning('Should have been on CardInformationPage.')
                    accounts_list.remove(card)
                    continue

                card.number = self.page.get_card_number(card)

                if not card.number:
                    # Cards without a number are not activated yet.
                    self.logger.warning("Card account doesn't have a card number.")
                    accounts_list.remove(card)

            type_with_iban = (
                Account.TYPE_CHECKING,
                Account.TYPE_SAVINGS,
                Account.TYPE_MARKET,
                Account.TYPE_PEA,
            )
            for account in accounts_list:
                if account.type in type_with_iban:
                    account_iban = self.iban.go(webid=account._webid).get_iban()
                    # IBAN fetching can fail randomly, let us try to fetch it
                    # again if we did not get it right the first time.
                    if account_iban == NotAvailable:
                        account_iban = self.iban.go(webid=account._webid).get_iban()
                    account.iban = account_iban

            for card in self.cards_list:
                checking, = [
                    account
                    for account in accounts_list
                    if account.type == Account.TYPE_CHECKING and account.url in card.url
                ]
                card.parent = checking

        if exc:
            raise exc

        self.ownership_guesser(accounts_list)
        return accounts_list

    def get_filled_accounts(self, pro=False):
        accounts_list = []
        if pro:
            owner_type = AccountOwnerType.ORGANIZATION
        else:
            owner_type = AccountOwnerType.PRIVATE
        for account in self.page.iter_accounts():
            account.owner_type = owner_type
            try:
                self.location(account.url)
            except requests.exceptions.HTTPError as e:
                # We do not yield life insurance accounts with a 404 or 503 error. Since we have verified, that
                # it is a website scoped problem and not a bad request from our part.
                # 404 is the original behavior. We could remove it in the future if it does not happen again.
                status_code = e.response.status_code
                if (
                    status_code in (404, 503)
                    and account.type == Account.TYPE_LIFE_INSURANCE
                ):
                    self.logger.warning(
                        '%s ! Broken link for life insurance account (%s). Account will be skipped',
                        status_code,
                        account.label,
                    )
                    continue
                raise

            self.page.fill_account(obj=account)
            if account.id:
                accounts_list.append(account)
        return accounts_list

    def get_account(self, account_id=None, account_iban=None):
        acc_list = self.get_accounts_list()
        account = strict_find_object(acc_list, id=account_id)
        if not account:
            account = strict_find_object(acc_list, iban=account_iban)
        return account

    def get_opening_date(self, account_url):
        self.location(account_url)
        return self.page.fetch_opening_date()

    def get_debit_date(self, debit_date):
        for i, j in zip(self.deferred_card_calendar, self.deferred_card_calendar[1:]):
            if i[0] < debit_date <= j[0]:
                return j[1]

    @retry_on_logout()
    @need_login
    def get_history(self, account, coming=False):
        if account.type in (
            Account.TYPE_LOAN,
            Account.TYPE_MORTGAGE,
            Account.TYPE_CONSUMER_CREDIT,
        ) or '/compte/derive' in account.url:
            return []
        if account.type is Account.TYPE_SAVINGS and "PLAN D'ÉPARGNE POPULAIRE" in account.label:
            return []
        if account.type in (Account.TYPE_LIFE_INSURANCE, Account.TYPE_MARKET, Account.TYPE_PER):
            return self.get_invest_transactions(account, coming)
        elif account.type == Account.TYPE_CARD:
            return self.get_card_transactions(account, coming)
        return self.get_regular_transactions(account, coming)

    def otp_location(self, *args, **kwargs):
        # this method is used in `otp_pagination` decorator from pages
        # without this header, we don't get a 401 but a 302 that logs us out
        kwargs.setdefault('headers', {}).update({'X-Requested-With': "XMLHttpRequest"})
        try:
            return super(BoursoramaBrowser, self).location(*args, **kwargs)
        except ClientError as e:
            # as done in boursorama's js : a 401 results in a popup
            # asking to send an otp to get more than x months of transactions
            # so... we don't want it :)
            if e.response.status_code != 401:
                raise e

    def get_regular_transactions(self, account, coming):
        # We look for 3 years of history.
        params = {}
        params['movementSearch[toDate]'] = (date.today() + relativedelta(days=40)).strftime('%d/%m/%Y')
        params['movementSearch[fromDate]'] = (date.today() - relativedelta(years=3)).strftime('%d/%m/%Y')
        params['movementSearch[selectedAccounts][]'] = account._webid
        if self.otp_location('%s/mouvements' % account.url.rstrip('/'), params=params) is None:
            return

        for transaction in self.page.iter_history():
            if coming == transaction._is_coming:
                yield transaction

            if coming and not transaction._is_coming:
                # end of coming, this is history
                break

    def get_html_past_card_transactions(self, account):
        """ Get card transactions from parent account page """

        self.otp_location('%s/mouvements' % account.parent.url.rstrip('/'))
        for tr in self.page.iter_history(is_card=False):
            # get card summaries
            if (
                tr.type == TransactionType.CARD_SUMMARY
                and account.number in tr.label  # in case of several cards per parent account
            ):
                tr.amount = - tr.amount
                yield tr

                # for each summaries, get detailed transactions
                self.location(tr._card_sum_detail_link)
                for detail_tr in self.page.iter_history():
                    detail_tr.date = tr.date
                    yield detail_tr

        # Note: Checking accounts have a 'Mes prélèvements à venir' tab,
        # but these transactions have no date anymore so we ignore them.

    def get_card_transaction(self, coming, tr):
        if coming and tr.date > date.today():
            tr._is_coming = True
            return True
        elif not coming and tr.date <= date.today():
            return True

    def get_card_transactions(self, account, coming):
        # All card transactions can be found in the CSV (history and coming),
        # however the CSV shows a maximum of 1000 transactions from all accounts.
        self.location(account.url)
        if self.home.is_here():
            # for some cards, the site redirects us to '/'...
            return

        if self.deferred_card_calendar is None:
            self.location(self.page.get_calendar_link())

        params = {}
        params['movementSearch[fromDate]'] = (date.today() - relativedelta(years=3)).strftime('%d/%m/%Y')
        params['fullSearch'] = 1
        if self.otp_location(account.url, params=params) is None:
            return

        csv_link = self.page.get_csv_link()
        if csv_link and self.otp_location(csv_link):
            # Yield past transactions as 'history' and
            # transactions in the future as 'coming':
            for tr in sorted_transactions(self.page.iter_history(account_number=account.number)):
                if self.get_card_transaction(coming, tr):
                    yield tr
        else:
            # if the export link is hidden or we got a 401 on csv link,
            # we need to get transactions from current page or we will just get nothing
            for tr in self.open(account.url).page.iter_history(is_card=True):
                if self.get_card_transaction(coming, tr):
                    yield tr

            if not coming:
                for tr in self.get_html_past_card_transactions(account):
                    yield tr

    def get_invest_transactions(self, account, coming):
        if coming:
            return
        transactions = []
        self.location('%s/mouvements' % account.url.rstrip('/'))
        account._history_pages = []
        for t in self.page.iter_history(account=account):
            transactions.append(t)
        for t in self.page.get_transactions_from_detail(account):
            transactions.append(t)
        for t in sorted(transactions, key=lambda tr: tr.date, reverse=True):
            yield t

    @retry_on_logout()
    @need_login
    def iter_investment(self, account):
        invest_account = (
            Account.TYPE_LIFE_INSURANCE,
            Account.TYPE_MARKET,
            Account.TYPE_PEA,
            Account.TYPE_PER,
        )

        if ('/compte/derive' not in account.url and account.type in invest_account):
            self.location(account.url)
            liquidity = self.page.get_liquidity()
            if liquidity:
                yield liquidity
            for inv in self.page.iter_investment():
                yield inv

    @retry_on_logout()
    @need_login
    def iter_market_orders(self, account):
        # Only Market & PEA accounts have the Market Orders tab
        if '/compte/derive' in account.url or account.type not in (Account.TYPE_MARKET, Account.TYPE_PEA):
            return []
        self.location(account.url)

        # Go to Market Orders tab ('Mes ordres')
        market_order_link = self.page.get_market_order_link()
        if not market_order_link:
            self.logger.warning('Could not find market orders link for account "%s".', account.label)
            return []
        self.location(market_order_link)
        return self.page.iter_market_orders()

    @need_login
    def get_profile(self):
        return self.profile.stay_or_go().get_profile()

    @need_login
    def get_advisor(self):
        # same for everyone
        advisor = Advisor()
        advisor.name = "Service clientèle"
        advisor.phone = "0146094949"
        return iter([advisor])

    def go_recipients_list(self, account_url, account_id, for_scheduled=False):
        # url transfer preparation
        url = urlsplit(account_url)
        parts = [part for part in url.path.split('/') if part]

        assert len(parts) > 2, 'Account url missing some important part to iter recipient'
        account_type = parts[1]  # cav, ord, epargne ...
        account_webid = parts[-1]

        # may raise a BrowserHTTPNotFound
        self.transfer_main_page.go(acc_type=account_type, webid=account_webid)

        # can check all account available transfer option
        if self.transfer_main_page.is_here():
            self.transfer_accounts.go(acc_type=account_type, webid=account_webid)

        if self.transfer_accounts.is_here():
            # may raise AccountNotFound
            self.page.submit_account(account_id)
        elif self.transfer_main_page.is_here():
            if for_scheduled:
                transfer_type = 'programme'
            else:
                transfer_type = 'immediat'
            self.new_transfer_wizard.go(
                acc_type=account_type,
                webid=account_webid,
                transfer_type=transfer_type
            )
            assert self.new_transfer_wizard.is_here(), 'Should be on recipients page'
            # may raise AccountNotFound
            self.page.submit_account(account_id)

        return account_type, account_webid

    @retry_on_logout()
    @need_login
    def iter_transfer_recipients(self, account, for_scheduled=False):
        if account.type in (Account.TYPE_LOAN, Account.TYPE_LIFE_INSURANCE):
            return []

        if not account.url:
            account = find_object(self.get_accounts_list(), iban=account.iban)
            assert account, 'Could not find an account with a matching iban'

        assert account.url, 'Account should have an url to access its recipients'

        try:
            self.go_recipients_list(account.url, account.id, for_scheduled)
        except (BrowserHTTPNotFound, AccountNotFound):
            return []

        assert (
            self.recipients_page.is_here()
            or self.new_transfer_wizard.is_here()
        ), 'Should be on recipients page'

        return self.page.iter_recipients()

    def check_basic_transfer(self, transfer):
        if transfer.date_type == TransferDateType.PERIODIC:
            raise NotImplementedError('Periodic transfer is not implemented')
        if transfer.amount <= 0:
            raise TransferInvalidAmount('transfer amount must be positive')
        if transfer.recipient_id == transfer.account_id:
            raise TransferInvalidRecipient('recipient must be different from emitter')
        if not transfer.label:
            raise TransferInvalidLabel('transfer label cannot be empty')

    @need_login
    def init_transfer(self, transfer, **kwargs):
        # Reset otp state when a new transfer is created
        self.transfer_form = None

        # Boursorama doesn't allow labels longer than 50 characters. To avoid
        # crash for such a useless problem, we truncate it.
        if len(transfer.label) > 50:
            self.logger.info('Truncating transfer label from "%s" to "%s"', transfer.label, transfer.label[:50])
            transfer.label = transfer.label[:50]

        # Transfer_date_type is set and used only for the new transfer wizard flow
        # the support for the old transfer wizard is left untouched as much as possible
        # until it can be removed.
        transfer_date_type = transfer.date_type
        if empty(transfer_date_type):
            if not empty(transfer.exec_date) and transfer.exec_date > date.today():
                transfer_date_type = TransferDateType.DEFERRED
            else:
                transfer_date_type = TransferDateType.FIRST_OPEN_DAY

        is_scheduled = (transfer_date_type in [TransferDateType.DEFERRED, TransferDateType.PERIODIC])

        self.check_basic_transfer(transfer)

        account = self.get_account(transfer.account_id, transfer.account_iban)
        if not account:
            raise AccountNotFound()

        recipients = list(self.iter_transfer_recipients(account, is_scheduled))
        if not recipients:
            raise TransferInvalidEmitter('The account cannot emit transfers')

        recipients = [rcpt for rcpt in recipients if rcpt.id == transfer.recipient_id]
        if len(recipients) == 0 and not empty(transfer.recipient_iban):
            # try to find recipients by iban:
            recipients = [rcpt for rcpt in recipients
                          if not empty(rcpt.iban) and rcpt.iban == transfer.recipient_iban]
        if len(recipients) == 0:
            raise TransferInvalidRecipient('The recipient cannot be used with the emitter account')
        assert len(recipients) == 1

        self.page.submit_recipient(recipients[0]._tempid)

        if self.transfer_characteristics.is_here():
            # Old transfer interface of Boursorama
            self.page.submit_info(transfer.amount, transfer.label, transfer.exec_date)
            assert self.transfer_confirm.is_here()

            if self.page.need_refresh():
                # In some case we are not yet in the transfer_characteristics page, you need to refresh the page
                self.location(self.url)
                assert not self.page.need_refresh()
            ret = self.page.get_transfer()

        else:
            # New transfer interface
            assert self.new_transfer_wizard.is_here()
            self.page.submit_amount(transfer.amount)

            assert self.new_transfer_wizard.is_here()
            if is_scheduled:
                self.page.submit_programme_date_type(transfer_date_type)

            self.page.submit_info(transfer.label, transfer_date_type, transfer.exec_date)

            fees = NotLoaded
            if self.new_transfer_estimate_fees.is_here():
                fees = self.page.get_transfer_fee()
                self.page.submit()

            transfer_error = self.page.get_errors()
            if transfer_error:
                raise TransferBankError(message=transfer_error)
            assert self.new_transfer_confirm.is_here()
            ret = self.page.get_transfer()

        ## Last checks to ensure that the confirmation matches what was expected

        # at this stage, the site doesn't show the real ids/ibans, we can only guess
        if recipients[0].label != ret.recipient_label:
            self.logger.info(
                'Recipients from iter_recipient and from the transfer are different: "%s" and "%s"',
                recipients[0].label, ret.recipient_label
            )
            if not ret.recipient_label.startswith('%s - ' % recipients[0].label):
                # the label displayed here is  "<name> - <bank>"
                # but in the recipients list it is "<name>"...
                raise AssertionError(
                    'Recipient label changed during transfer (from "%s" to "%s")'
                    % (recipients[0].label, ret.recipient_label)
                )
        ret.recipient_id = recipients[0].id
        ret.recipient_iban = recipients[0].iban

        if account.label != ret.account_label:
            raise TransferError('Account label changed during transfer (from "%s" to "%s")'
                                % (account.label, ret.account_label))

        ret.account_id = account.id
        ret.account_iban = account.iban

        if not empty(fees) and empty(ret.fees):
            ret.fees = fees

        return ret

    def otp_validation_continue_transfer(self, transfer, **kwargs):
        """Send any otp validation code that was provided to continue transfer

        This page should not have "@need_login", as a "relogin" would void
        the validity of any existing otp code.
        """
        otp_code = kwargs.get('otp_sms', kwargs.get('otp_email'))
        if not otp_code:
            return False

        if not self.transfer_form:
            # The session expired
            raise TransferTimeout()

        # Continue a previously initiated transfer after an otp step
        # once the otp is validated, we should be redirected to the
        # transfer sent page
        self.send_otp_data(self.transfer_form, otp_code, TransferBankError)
        self.transfer_form = None
        return True

    @need_login
    def execute_transfer(self, transfer, **kwargs):
        # If we are in the case of continuation after an otp, we will already
        # be on the transfer_sent page, otherwise, confirmation has to be sent
        if self.transfer_confirm.is_here() or self.new_transfer_confirm.is_here():
            self.page.submit()

        assert self.transfer_sent.is_here() or self.new_transfer_sent.is_here()

        transfer_error = self.page.get_errors()
        if transfer_error:
            raise TransferBankError(message=transfer_error)

        if not self.page.is_confirmed():
            # Check if an otp step might be needed initially or subsequently after a
            # previous otp step (ex.: email after sms)
            self.transfer_form, otp_field_value = self.check_and_initiate_otp(None)
            if self.transfer_form:
                raise TransferStep(transfer, otp_field_value)

            # We are not sure if the transfer was successful or not, so raise an error
            raise AssertionError('Confirmation message not found inside transfer sent page')

        # The last page contains no info, return the last transfer object from init_transfer
        return transfer

    @need_login
    def init_new_recipient(self, recipient):
        # so it is reset when a new recipient is added
        self.recipient_form = None

        # get url
        # If an account was provided for the recipient, use it
        # otherwise use the first checking account available
        account = None
        for account in self.get_accounts_list():
            if not account.url:
                continue
            if recipient.origin_account_id is None:
                if account.type == Account.TYPE_CHECKING:
                    break
            elif account.id == recipient.origin_account_id:
                break
            elif (not empty(recipient.origin_account_iban)
                  and not empty(account.iban)
                  and account.iban == recipient.origin_account_iban):
                break
        else:
            raise AddRecipientBankError(message="Compte ne permettant pas l'ajout de bénéficiaires")

        try:
            self.go_recipients_list(account.url, account.id)
        except AccountNotFound:
            raise AddRecipientBankError(message="Compte ne permettant pas d'emettre des virements")

        assert (
            self.recipients_page.is_here()
            or self.new_transfer_wizard.is_here()
        ), 'Should be on recipients page'

        if not self.page.is_new_recipient_allowed():
            raise AddRecipientBankError(message="Compte ne permettant pas l'ajout de bénéficiaires")

        target = '%s/virements/comptes-externes/nouveau' % account.url.rstrip('/')
        self.location(target)

        assert self.page.is_characteristics(), 'Not on the page to add recipients.'

        # fill recipient form
        self.page.submit_recipient(recipient)
        if recipient.origin_account_id is None:
            recipient.origin_account_id = account.id

        # Go to recipient confirmation page that will request to send an sms
        assert self.page.is_confirm_send_sms(), 'Cannot reach the page asking to send a sms.'
        self.page.confirm_send_sms()

        otp_forms, otp_field_value = self.check_and_initiate_otp(account.url)
        if otp_forms:
            self.recipient_form = otp_forms
            raise AddRecipientStep(recipient, otp_field_value)

        # in the unprobable case that no otp was needed, go on
        return self.check_and_update_recipient(recipient, account.url, account)

    def new_recipient(self, recipient, **kwargs):
        otp_code = kwargs.get('otp_sms', kwargs.get('otp_email'))
        if not otp_code:
            # step 1 of new recipient
            return self.init_new_recipient(recipient)

        # step 2 of new_recipient
        if not self.recipient_form:
            # The session expired
            raise AddRecipientTimeout()

        # there is no confirmation to check the recipient
        # validating the sms code directly adds the recipient
        account_url = self.send_otp_data(self.recipient_form, otp_code, AddRecipientBankError)
        self.recipient_form = None

        # Check if another otp step might be needed (ex.: email after sms)
        self.recipient_form, otp_field_value = self.check_and_initiate_otp(account_url)
        if self.recipient_form:
            raise AddRecipientStep(recipient, otp_field_value)

        return self.check_and_update_recipient(recipient, account_url)

    def send_otp_data(self, otp_data, otp_code, exception):

        # Validate the OTP
        confirm_data = otp_data['confirm_data']
        confirm_data['token'] = otp_code
        url = confirm_data['url']

        try:
            self.location(url, data=confirm_data)
        except ServerError as e:
            # If the code is invalid, we have an error 503
            if e.response.status_code == 503:
                raise exception(message=e.response.json()['error']['message'])
            raise

        del otp_data['confirm_data']
        account_url = otp_data.pop('account_url')

        # Continue the navigation by sending the form data
        # we saved.
        html_page_form = otp_data.pop('html_page_form')
        url = html_page_form.pop('url')
        self.location(url, data=html_page_form)

        return account_url

    def check_and_initiate_otp(self, account_url):
        """Trigger otp if it is needed

        An otp will be requested after confirmation for adding a new recipient,
        transfering to an unregistered recipient, or sending an important amount
        (ex.: 60 000).
        Usually the otp is an sms, eventually followed by an email otp.
        Observed behaviors:
        - if the add recipient is restarted after the sms has been confirmed
        recently, the sms step is not presented again.
        - Sometimes after validating the sms code, the user is also asked to
        validate a code received by email (observed when adding a non-french
        recipient).
        """
        if self.page.is_send_sms():
            otp_name = 'sms'
            otp_field_value = Value('otp_sms', label='Veuillez saisir le code reçu par sms')
        elif self.page.is_send_email():
            otp_name = 'email'
            otp_field_value = Value('otp_email', label='Veuillez saisir le code reçu par email')
        elif self.page.is_send_app():
            raise AuthMethodNotImplemented('Lʼauthentification renforcée par application mobile nʼest pas encore prise en charge.')
        else:
            return None, None

        otp_data = {'account_url': account_url}

        otp_data['html_page_form'] = self.page.get_confirm_otp_form()
        otp_data['confirm_data'] = self.page.get_confirm_otp_data()

        self.page.send_otp()
        assert self.page.is_confirm_otp(), 'The %s was not sent.' % otp_name

        return otp_data, otp_field_value

    def check_and_update_recipient(self, recipient, account_url, account=None):
        assert self.page.is_created(), 'The recipient was not added.'

        # At this point, the recipient was added to the website,
        # here we just want to return the right Recipient object.
        # We are taking it from the recipient list page
        # because there is no summary of the adding

        if not account:
            account = self.get_account(recipient.origin_account_id, recipient.origin_account_iban)
            if not account:
                raise AccountNotFound()

        self.go_recipients_list(account_url, account.id)
        assert (
            self.recipients_page.is_here()
            or self.new_transfer_wizard.is_here()
        ), 'Should be on recipients page'
        return find_object(self.page.iter_recipients(), iban=recipient.iban, error=RecipientNotFound)

    @need_login
    def iter_transfers(self, account):
        if account is not None:
            if not (isinstance(account, Account) or isinstance(account, Emitter)):
                self.logger.debug('we have only the emitter id %r, fetching full object', account)
                account = find_object(self.iter_emitters(), id=account)

            return sorted_transfers(self.iter_transfers_for_emitter(account))

        transfers = []
        self.logger.debug('no account given: fetching all emitters')
        for emitter in self.iter_emitters():
            self.logger.debug('fetching transfers for emitter %r', emitter.id)
            transfers.extend(self.iter_transfers_for_emitter(emitter))
        transfers = sorted_transfers(transfers)
        return transfers

    @need_login
    def iter_transfers_for_emitter(self, emitter):
        # We fetch original transfers from 2 pages (single transfers vs periodic).
        # Each page is sorted, but since we list from the 2 pages in sequence,
        # the result is not sorted as is.
        # TODO Maybe the site is not stateful and we could do parallel navigation
        # on both lists, to merge the sorted iterators.

        self.transfer_list.go(acc_type='temp', webid=emitter._bourso_id, type='ponctuels')
        for transfer in self.page.iter_transfers():
            transfer.account_id = emitter.id
            transfer.date_type = TransferDateType.FIRST_OPEN_DAY
            if transfer._is_instant:
                transfer.date_type = TransferDateType.INSTANT
            elif transfer.exec_date > date.today():
                # The site does not indicate when transfer was created
                # we only have the date of its execution.
                # So, for a DONE transfer, we cannot know if it was deferred or not...
                transfer.date_type = TransferDateType.DEFERRED

            self.location(transfer.url)
            self.page.fill_transfer(obj=transfer)

            # build id with account id because get_transfer will receive only the account id
            assert transfer.id, 'transfer should have an id from site'
            transfer.id = '%s.%s' % (emitter.id, transfer.id)
            yield transfer

        self.transfer_list.go(acc_type='temp', webid=emitter._bourso_id, type='permanents')
        for transfer in self.page.iter_transfers():
            transfer.account_id = emitter.id
            transfer.date_type = TransferDateType.PERIODIC
            self.location(transfer.url)
            self.page.fill_transfer(obj=transfer)
            self.page.fill_periodic_transfer(obj=transfer)

            assert transfer.id, 'transfer should have an id from site'
            transfer.id = '%s.%s' % (emitter.id, transfer.id)
            yield transfer

    def iter_currencies(self):
        return self.currencylist.go().get_currency_list()

    def get_rate(self, curr_from, curr_to):
        r = Rate()
        params = {
            'from': curr_from,
            'to': curr_to,
            'amount': '1',
        }
        r.currency_from = curr_from
        r.currency_to = curr_to
        r.datetime = datetime.now()
        try:
            self.currencyconvert.go(params=params)
            r.value = self.page.get_rate()
        # if a rate is no available the site return a 401 error...
        except ClientError:
            return
        return r

    @need_login
    def iter_emitters(self):
        # It seems that if we give a wrong acc_type and webid to the transfer page
        # we are redirected to a page where we can choose the emitter account
        self.transfer_accounts.go(acc_type='temp', webid='temp')
        if self.transfer_main_page.is_here():
            self.new_transfer_wizard.go(acc_type='temp', webid='temp', transfer_type='immediat')
        return self.page.iter_emitters()

    @retry_on_logout()
    @need_login
    def iter_subscriptions(self):
        self.statements_page.go()
        return self.page.iter_subscriptions()

    @need_login
    def iter_documents(self, subscription):
        self.rib_page.go()
        for doc in self.page.get_document(subid=subscription.id):
            yield doc

        self.statements_page.go()
        page = self.page.submit_form(subscription._account_key).page
        for doc in page.iter_documents(subid=subscription.id):
            yield doc
