# -*- coding: utf-8 -*-

# Copyright(C) 2010-2011 Jocelyn Jaubert
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

import time
from datetime import datetime
from decimal import Decimal

from dateutil.relativedelta import relativedelta

from woob.browser import URL, need_login
from woob.browser.mfa import TwoFactorBrowser
from woob.capabilities.bill import Document, DocumentTypes
from woob.exceptions import (
    BrowserIncorrectPassword, ActionNeeded, ActionType, BrowserUnavailable,
    AppValidation, AppValidationError, AppValidationCancelled,
    AppValidationExpired, BrowserPasswordExpired, BrowserUserBanned,
    OTPSentType, SentOTPQuestion,
)
from woob.capabilities.bank import (
    Account, TransferBankError, AddRecipientStep,
    TransactionType, AccountOwnerType, Loan,
)
from woob.capabilities.base import NotAvailable
from woob.browser.exceptions import BrowserHTTPNotFound, ClientError
from woob.capabilities.profile import ProfileMissing
from woob.tools.value import Value, ValueBool
from woob.tools.decorators import retry

from .pages.accounts_list import (
    AccountsMainPage, AccountDetailsPage, AccountsPage, LoansPage, HistoryPage,
    CardHistoryPage, PeaLiquidityPage, MarketOrderPage, MarketOrderDetailPage,
    AdvisorPage, HTMLProfilePage, CreditPage, CreditHistoryPage, OldHistoryPage,
    MarketPage, LifeInsurance, LifeInsuranceHistory, LifeInsuranceInvest, LifeInsuranceInvest2,
    LifeInsuranceAPI, LifeInsuranceInvestAPI, LifeInsuranceInvestAPI2, LifeInsuranceInvestDetailsAPI,
    UnavailableServicePage, TemporaryBrowserUnavailable, RevolvingDetailsPage,
)
from .pages.transfer import AddRecipientPage, SignRecipientPage, TransferJson, SignTransferPage
from .pages.login import (
    MainPage, LoginPage, BadLoginPage, ReinitPasswordPage,
    ActionNeededPage, ErrorPage, VkImage, SkippableActionNeededPage,
)
from .pages.subscription import DocumentsPage, RibPdfPage


__all__ = ['SocieteGenerale']


class SocieteGeneraleTwoFactorBrowser(TwoFactorBrowser):
    HAS_CREDENTIALS_ONLY = True

    polling_transaction = None
    polling_duration = 300  # default to 5 minutes
    __states__ = ('polling_transaction',)
    skippable_action_needed_page = URL(
        r'/icd/gax/data/users/administration/out-of-remedy-security-security-zone.json',
        SkippableActionNeededPage
    )

    def __init__(self, config, *args, **kwargs):
        super(SocieteGeneraleTwoFactorBrowser, self).__init__(config, *args, **kwargs)

        self.AUTHENTICATION_METHODS = {
            'resume': self.handle_polling,
            'code': self.handle_sms,
        }

    def load_state(self, state):
        if state.get('polling_transaction'):
            # can't start in the middle of a AppValidation process
            # or we will launch another one with that URL
            state.pop('url', None)
        super(SocieteGeneraleTwoFactorBrowser, self).load_state(state)

    def clear_init_cookies(self):
        # Keep the 2FA cookie(s) to prevent a 2FA trigger
        cookies_to_keep = []
        for cookie in self.session.cookies:
            if cookie.name.startswith('NAVID-'):
                cookies_to_keep.append(cookie)
        super().clear_init_cookies()
        if len(cookies_to_keep) > 0:
            for cookie in cookies_to_keep:
                self.session.cookies.set_cookie(cookie)

    def check_password(self):
        if not self.password.isdigit() or len(self.password) not in (6, 7):
            raise BrowserIncorrectPassword()
        if not self.username.isdigit() or len(self.username) < 8:
            raise BrowserIncorrectPassword()

    def check_login_reason(self):
        reason = self.page.get_reason()
        if reason is not None:
            # 'reason' doesn't bear a user-friendly message.
            # The messages related to each 'reason' can be found in 'swm.main.js'
            if reason == 'echec_authent':
                raise BrowserIncorrectPassword()
            elif reason == 'mdptmp_expire':
                raise BrowserPasswordExpired()
            elif reason == 'acces_bloq':
                raise BrowserUserBanned(
                    "Suite à trois saisies erronées de vos codes, l'accès à vos comptes est bloqué jusqu'à demain pour des raisons de sécurité."
                )
            elif reason in ('acces_susp', 'pas_acces_bad'):
                # These codes are not related to any valuable messages,
                # just "Votre accès est suspendu. Vous n'êtes pas autorisé à accéder à l'application."
                raise BrowserUserBanned()
            elif reason in ('err_is', 'err_tech'):
                # there is message "Service momentanément indisponible. Veuillez réessayer."
                # in SG website in that case ...
                raise BrowserUnavailable()

            raise AssertionError('Unhandled error reason: %s' % reason)

    def check_auth_method(self):
        auth_method = self.page.get_auth_method()

        if not auth_method:
            self.logger.warning('No auth method available !')
            raise ActionNeeded(
                locale="fr-FR", message="Veuillez ajouter un numéro de téléphone sur votre banque et/ou activer votre Pass Sécurité.",
                action_type=ActionType.ENABLE_MFA,
            )

        if auth_method['unavailability_reason'] == "ts_non_enrole":
            raise ActionNeeded(
                locale="fr-FR", message="Veuillez ajouter un numéro de téléphone sur votre banque.",
                action_type=ActionType.ENABLE_MFA,
            )

        elif auth_method['unavailability_reason']:
            raise AssertionError('Unknown unavailability reason "%s" found' % auth_method['unavailability_reason'])

        if auth_method['type_proc'].lower() == 'auth_oob':
            # notification is sent here
            self.location('/sec/oob_sendooba.json', method='POST', headers={'Content-Type': 'application/x-www-form-urlencoded'})

            donnees = self.page.doc['donnees']
            self.polling_transaction = donnees['id-transaction']

            if donnees.get('expiration_date_hh') and donnees.get('expiration_date_mm'):
                now = datetime.now()
                expiration_date = now.replace(
                    hour=int(donnees['expiration_date_hh']),
                    minute=int(donnees['expiration_date_mm'])
                )
                self.polling_duration = int((expiration_date - now).total_seconds())

            message = "Veuillez valider l'opération dans votre application"
            # several terminals can be associated with that user
            terminals = [terminal['nom'] for terminal in auth_method['terminal'] if terminal.get('nom')]
            if terminals:
                message += " sur l'un de vos périphériques actifs: " + ', '.join(terminals)

            # We reset the current browser page. The next navigation on a '@need_login' page will trigger
            # the verification of the logged-in status. This will fail, and enter the `do_login` procedure.
            # Cf `need_login()` in `woob/browser/browsers.py`
            self.page = None

            raise AppValidation(message)

        elif auth_method['type_proc'].lower() == 'auth_csa':
            if auth_method['mode'] == "SMS":
                # SMS is sent here
                self.location(
                    '/sec/csa/send.json',
                    data={'csa_op': "auth"}
                )

                # We reset the current browser page. The next navigation on a '@need_login' page will trigger
                # the verification of the logged-in status. This will fail, and enter the `do_login` procedure.
                # Cf `need_login()` in `woob/browser/browsers.py`
                self.page = None

                raise SentOTPQuestion(
                    field_name='code',
                    medium_type=OTPSentType.SMS,
                    medium_label=auth_method['ts'],
                    message='Entrez le Code Sécurité reçu par SMS sur le numéro ' + auth_method['ts'],
                )

            self.logger.warning('Unknown CSA method "%s" found', auth_method['mod'])

        else:
            self.logger.warning('Unknown sign method "%s" found', auth_method['type_proc'])

        raise AssertionError('Unknown auth method "%s: %s" found' % (auth_method['type_proc'], auth_method.get('mod')))

    def check_skippable_action_needed(self):
        if not self.login.is_here():
            return

        reason = self.page.get_skippable_action_needed()
        if reason == 'FIABILISATION_TS':
            self.skippable_action_needed_page.go(
                headers={'Content-Type': 'application/json;charset=UTF-8'},
                data='',
            )
            # Sometimes it is not possible to skip this step without SCA
            if self.page.has_twofactor():
                self.check_interactive()
                self.check_auth_method()

    def init_login(self):
        self.check_password()

        self.main_page.go()
        try:
            self.page.login(self.username[:8], self.password)
        except BrowserHTTPNotFound:
            raise BrowserIncorrectPassword()

        assert self.login.is_here(), "An error has occurred, we should be on login page."

        self.check_login_reason()

        if self.page.has_twofactor():
            self.check_interactive()
            self.check_auth_method()

        self.check_skippable_action_needed()

    def check_polling_errors(self, status):
        if status == "rejected":
            raise AppValidationCancelled(
                "L'opération dans votre application a été annulée"
            )

        if status == "aborted":
            raise AppValidationExpired(
                "L'opération dans votre application a expiré"
            )

        if status != "available":
            raise AppValidationError()

    def handle_polling(self):
        assert self.polling_transaction, "polling_transaction is mandatory !"

        data = {'n10_id_transaction': self.polling_transaction}
        timeout = time.time() + self.polling_duration
        while time.time() < timeout:
            self.location('/sec/oob_pollingooba.json', data=data)

            status = self.page.doc['donnees']['transaction_status']
            if status != "in_progress":
                break

            time.sleep(3)
        else:
            status = "aborted"

        self.check_polling_errors(status)

        data['oob_op'] = "auth"
        self.location('/sec/oob_auth.json', data=data)

        if self.page.doc.get('commun', {}).get('statut').lower() == "nok":
            raise BrowserUnavailable()

        self.polling_transaction = None

        self.check_skippable_action_needed()

        # Need to end up on a LoggedPage to avoid starting back at login
        # Might be caused by multiple @need_login call
        self.accounts.go()

    def handle_sms(self):
        if len(self.code) != 6:
            raise BrowserIncorrectPassword(
                'Le Code Sécurité doit avoir une taille de 6 caractères'
            )

        data = {
            'code': self.code,
            'csa_op': "auth",
        }
        self.location('/sec/csa/check.json', data=data)

        if self.page.doc.get('commun', {}).get('statut').lower() == "nok":
            raise BrowserIncorrectPassword('Le Code Sécurité est invalide')

        self.check_skippable_action_needed()


class SocieteGenerale(SocieteGeneraleTwoFactorBrowser):
    BASEURL = 'https://particuliers.sg.fr'
    STATE_DURATION = 10
    TWOFA_DURATION = 60 * 24 * 90

    # documents
    documents = URL(r'/icd/epe/data/get-all-releves-authsec.json', DocumentsPage)
    pdf_page = URL(
        r'/icd/epe/pdf/edocument-authsec.pdf\?b64e200_prestationIdTechnique=(?P<id_tech>.*)&b64e200_refTechnique=(?P<ref_tech>.*)'
    )
    rib_pdf_page = URL(r'/com/icd-web/cbo/pdf/rib-authsec.pdf', RibPdfPage)

    # Bank
    accounts_main_page = URL(
        r'/restitution/cns_listeprestation.html',
        r'/com/icd-web/cbo/index.html',
        r'/icd/cbo/index-authsec.html',
        AccountsMainPage
    )
    account_details_page = URL(r'/restitution/cns_detailPrestation.html', AccountDetailsPage)
    accounts = URL(r'/icd/cbo/data/liste-prestations-authsec.json\?n10_avecMontant=1', AccountsPage)
    history = URL(r'/icd/cbo/data/liste-operations-authsec.json', HistoryPage)
    loans = URL(r'/icd/espaces-thematiques/data/getLoansRecovery.json', LoansPage)
    revolving_rate = URL(r'icd/cbo/data/recapitulatif-prestation-authsec.json', RevolvingDetailsPage)

    card_history = URL(r'/restitution/cns_listeReleveCarteDd.xml', CardHistoryPage)
    credit = URL(r'/restitution/cns_detailAVPAT.html', CreditPage)
    credit_history = URL(r'/restitution/cns_listeEcrCav.xml', CreditHistoryPage)
    old_hist_page = URL(
        r'/restitution/cns_detailPep.html',
        r'/restitution/cns_listeEcrPep.html',
        r'/restitution/cns_detailAlterna.html',
        r'/restitution/cns_listeEncoursAlterna.html',
        OldHistoryPage
    )

    # Recipient
    add_recipient = URL(
        r'/personnalisation/per_cptBen_ajouterFrBic.html',
        r'/lgn/url.html',
        AddRecipientPage
    )
    json_recipient = URL(
        r'/sec/getsigninfo.json',
        r'/sec/csa/send.json',
        r'/sec/oob_sendoob.json',
        r'/sec/oob_polling.json',
        SignRecipientPage
    )
    # Transfer
    json_transfer = URL(
        r'/icd/vupri/data/vupri-liste-comptes.json\?an200_isBack=false',
        r'/icd/vupri/data/vupri-check.json',
        TransferJson
    )
    sign_transfer = URL(r'/icd/vupri/data/vupri-generate-token.json', SignTransferPage)
    confirm_transfer = URL(r'/icd/vupri/data/vupri-save.json', TransferJson)

    # Wealth
    market = URL(r'/brs/cct/comti20.html', MarketPage)
    pea_liquidity = URL(r'/restitution/cns_detailPea.html', PeaLiquidityPage)
    life_insurance = URL(
        r'/asv/asvcns10.html',
        r'/asv/AVI/asvcns10a.html',
        r'/brs/fisc/fisca10a.html',
        LifeInsurance
    )
    life_insurance_invest = URL(r'/asv/AVI/asvcns20a.html', LifeInsuranceInvest)
    life_insurance_invest_2 = URL(r'/asv/PRV/asvcns10priv.html', LifeInsuranceInvest2)
    auth_life_insurance_api = URL(r'/icd/avd/index-authsec.html')
    life_insurance_api = URL(
        r'/icd/avd/data/api/v1/prestation-assurance-vie-authsec.json\?b64e200_hashIdPrestation=(?P<id_tech>.*)',
        LifeInsuranceAPI
    )
    life_insurance_invest_api = URL(
        r'/icd/avd/data/api/v1/detail-contrat-assurance-vie-authsec.json',
        LifeInsuranceInvestAPI
    )
    life_insurance_invest_api_2 = URL(
        r'/icd/avd/data/api/v1/contrat-assurance-vie-authsec.json',
        LifeInsuranceInvestAPI2
    )
    life_insurance_invest_details_api = URL(
        r'/icd/avd/data/api/v1/performances-authsec.json\?b64e200_hashIdPrestation=(?P<id_tech>.*)',
        LifeInsuranceInvestDetailsAPI
    )
    life_insurance_history = URL(r'/asv/AVI/asvcns2(?P<n>[0-9])c.html', LifeInsuranceHistory)
    market_orders = URL(r'/brs/suo/suivor20.html', MarketOrderPage)
    market_orders_details = URL(r'/brs/suo/suivor30.html', MarketOrderDetailPage)

    # Profile
    advisor = URL(r'/icd/pon/data/get-contacts.xml', AdvisorPage)
    html_profile_page = URL(r'/com/dcr-web/dcr/dcr-coordonnees.html', HTMLProfilePage)

    bad_login = URL(r'/acces/authlgn.html', r'/error403.html', BadLoginPage)
    reinit = URL(
        r'/acces/changecodeobligatoire.html',
        r'/swm/swm-changemdpobligatoire.html',
        ReinitPasswordPage
    )
    action_needed = URL(
        r'/com/icd-web/forms/cct-index.html',
        r'/com/icd-web/gdpr/gdpr-recueil-consentements.html',
        r'/com/icd-web/forms/kyc-index.html',
        ActionNeededPage
    )
    unavailable_service_page = URL(
        r'/com/service-indisponible.html',
        r'.*/Technical-pages/503-error-page/unavailable.html',
        r'.*/Technical-pages/service-indisponible/service-indisponible.html',
        r'/fonction-indisponible',
        UnavailableServicePage
    )
    error = URL(
        r'https://static.sg.fr/pri/erreur.html',
        r'https://.*/pri/erreur.html',
        ErrorPage
    )
    login = URL(
        r'https://particuliers.sg.fr//sec/vk/',  # yes, it works only with double slash
        r'/sec/oob_sendooba.json',
        r'/sec/oob_pollingooba.json',
        r'/sec/oob_auth.json',
        r'/sec/csa/check.json',
        LoginPage
    )
    vk_image = URL(r'/?/sec/vkm/gen_ui', VkImage)
    main_page = URL(r'https://particuliers.sg.fr', MainPage)

    context = None
    dup = None
    id_transaction = None

    def __init__(self, config, *args, **kwargs):
        super(SocieteGenerale, self).__init__(config, *args, **kwargs)

        self.__states__ += ('context', 'dup', 'id_transaction',)

    def transfer_condition(self, state):
        return state.get('dup') is not None and state.get('context') is not None

    def locate_browser(self, state):
        if self.transfer_condition(state):
            self.location('/com/icd-web/cbo/index.html')
        elif all(url in state['url'] for url in self.login.urls):
            return
        elif self.json_recipient.match(state['url']):
            return
        super(SocieteGenerale, self).locate_browser(state)

    def iter_cards(self, account):
        for el in account._cards:
            if el['carteDebitDiffere']:
                card = Account()
                card.id = el['id']
                card.number = el['numeroCompteFormate'].replace(' ', '')
                card.label = el['labelToDisplay']
                card.balance = Decimal('0')
                card.coming = Decimal(str(el['montantProchaineEcheance']))
                card.type = Account.TYPE_CARD
                card.currency = account.currency
                card._internal_id = el['idTechnique']
                card._prestation_id = el['id']
                card.owner_type = AccountOwnerType.PRIVATE
                yield card

    def switch_account_to_loan(self, account):
        loan = Loan()
        copy_attrs = (
            'id', 'number', 'label', 'type', 'ownership', 'owner_type',
            'coming', '_internal_id', '_prestation_id', '_loan_type',
            '_is_json_histo',
        )
        for attr in copy_attrs:
            setattr(loan, attr, getattr(account, attr))

        return loan

    @need_login
    def get_accounts_list(self):
        self.accounts_main_page.go()
        self.page.is_accounts()

        if self.page.is_old_website():
            # go on new_website
            self.location(self.absurl('/com/icd-web/cbo/index.html'))

        go = retry(TemporaryBrowserUnavailable)(self.accounts.go)
        go()

        if not self.page.is_new_website_available():
            # return in old pages to get accounts
            self.accounts_main_page.go(params={'NoRedirect': True})
            for acc in self.page.iter_accounts():
                yield acc
            return

        accounts = {}
        for account in self.page.iter_accounts():
            account._loan_parent_id = None
            account.owner_type = AccountOwnerType.PRIVATE
            for card in self.iter_cards(account):
                card.parent = account
                card.ownership = account.ownership
                card.owner_type = AccountOwnerType.PRIVATE
                yield card

            if account.type in (
                account.TYPE_LOAN,
                account.TYPE_CONSUMER_CREDIT,
                account.TYPE_REVOLVING_CREDIT,
                account.TYPE_MORTGAGE,
            ):
                loan = self.switch_account_to_loan(account)
                self.loans.stay_or_go()
                self.page.get_loan_details(loan)

                # The revolving rate is missing on this page.
                # We have to go to the revolving details page for each revolving.
                if loan.type == account.TYPE_REVOLVING_CREDIT:
                    self.revolving_rate.go(params={'b64e200_prestationIdTechnique': account._internal_id})
                    self.page.get_revolving_rate(loan)

                accounts[account.id] = loan

            else:
                accounts[account.id] = account

        # Adding parent account to LOAN account
        for account in accounts.values():
            if account._loan_parent_id:
                account.parent = accounts.get(account._loan_parent_id, NotAvailable)

            yield account

    def fill_loan_insurance(self, loan):
        if not loan.parent:
            self.logger.info('Loan: %s has no parent account. Could not find insurance amount', loan)
            return

        for transaction in self.iter_history(loan.parent):
            if tr_loan := transaction._loan:
                if tr_loan.id in loan.id:  # Why not equal though?
                    for field, value in loan.iter_fields():
                        if not value:
                            new_value = getattr(tr_loan, field, None)
                            if new_value:
                                setattr(loan, field, new_value)
                    break

                if not loan.insurance_amount:
                    self.logger.info(
                        'A transaction related to the loan %s was found, but has no insurance amount. transaction raw: %s',
                        loan,
                        transaction.raw,
                    )
                    break
        else:
            self.logger.info('No transaction related to the loan %s was found.', loan)

    def next_page_retry(self, condition):
        next_page = self.page.hist_pagination(condition)
        if next_page:
            location = retry(TemporaryBrowserUnavailable)(self.location)
            location(next_page)
            return True
        return False

    @need_login
    def iter_history(self, account):
        if account.type in (
            account.TYPE_LOAN,
            account.TYPE_MARKET,
            account.TYPE_CONSUMER_CREDIT,
            account.TYPE_MORTGAGE,
        ):
            return

        if account.type == Account.TYPE_PEA and not ('Espèces' in account.label or 'ESPECE' in account.label):
            return

        if not account._internal_id:
            raise BrowserUnavailable()

        transfer_recipients = list(self.iter_recipients(account))

        # get history for account on old website
        # request to get json is not available yet, old request to get html response
        if any((
                account.type in (account.TYPE_LIFE_INSURANCE, account.TYPE_PERP, account.TYPE_PER),
                account.type == account.TYPE_REVOLVING_CREDIT and account._loan_type != 'PR_CONSO',
                account.type in (account.TYPE_REVOLVING_CREDIT, account.TYPE_SAVINGS) and not account._is_json_histo,
        )):
            go = retry(TemporaryBrowserUnavailable)(self.account_details_page.go)
            go(params={'idprest': account._prestation_id})

            if self.unavailable_service_page.is_here():
                raise BrowserUnavailable()

            history_url = self.page.get_history_url()

            # history_url return NotAvailable when history page doesn't exist
            # it return None when we don't know if history page exist
            if history_url is None:
                error_msg = self.page.get_error_msg()
                assert error_msg, 'There should have error or history url'
                raise BrowserUnavailable(error_msg)
            elif history_url:
                self.location(self.absurl(history_url))

            for tr in self.page.iter_history(transfer_recipients=transfer_recipients):
                yield tr
            return

        if account.type == account.TYPE_CARD:
            go = retry(TemporaryBrowserUnavailable)(self.history.go)
            go(params={'b64e200_prestationIdTechnique': account.parent._internal_id})

            next_page = True
            while next_page:
                for summary_card_tr in self.page.iter_card_transactions(card_number=account.number):
                    yield summary_card_tr

                    for card_tr in summary_card_tr._card_transactions:
                        card_tr.date = summary_card_tr.date
                        # We use the Raw pattern to set the rdate automatically, but that make
                        # the transaction type to "CARD", so we have to correct it in the browser.
                        card_tr.type = TransactionType.DEFERRED_CARD
                        yield card_tr
                next_page = self.next_page_retry('history')
            return

        go = retry(TemporaryBrowserUnavailable)(self.history.go)
        go(params={'b64e200_prestationIdTechnique': account._internal_id})

        next_page = True
        while next_page:
            for transaction in self.page.iter_history(transfer_recipients=transfer_recipients):
                yield transaction
            next_page = self.next_page_retry('history')

    @need_login
    def iter_coming(self, account):
        skipped_types = (
            Account.TYPE_LOAN,
            Account.TYPE_MARKET,
            Account.TYPE_PEA,
            Account.TYPE_LIFE_INSURANCE,
            Account.TYPE_REVOLVING_CREDIT,
            Account.TYPE_CONSUMER_CREDIT,
            Account.TYPE_MORTGAGE,
            Account.TYPE_PERP,
        )
        if account.type in skipped_types:
            return

        if not account._internal_id:
            raise BrowserUnavailable()

        if account.type == account.TYPE_SAVINGS and not account._is_json_histo:
            # Waiting for account with transactions
            return

        internal_id = account._internal_id
        if account.type == account.TYPE_CARD:
            internal_id = account.parent._internal_id

        go = retry(TemporaryBrowserUnavailable)(self.history.go)
        go(params={'b64e200_prestationIdTechnique': internal_id})

        if account.type == account.TYPE_CARD:
            next_page = True
            while next_page:
                for transaction in self.page.iter_future_transactions(acc_prestation_id=account._prestation_id):
                    # coming transactions on this page are not included in coming balance
                    # use it only to retrive deferred card coming transactions
                    if transaction._card_coming:
                        for card_coming in transaction._card_coming:
                            card_coming.date = transaction.date
                            # We use the Raw pattern to set the rdate automatically, but that makes
                            # the transaction type to "CARD", so we have to correct it in the browser.
                            card_coming.type = TransactionType.DEFERRED_CARD
                            yield card_coming
                next_page = self.next_page_retry('future')
            return

        next_page = True
        while next_page:
            for intraday_tr in self.page.iter_intraday_comings():
                yield intraday_tr
            next_page = self.next_page_retry('intraday')

    @need_login
    def iter_investment(self, account):
        if account.type not in (
            Account.TYPE_MARKET, Account.TYPE_LIFE_INSURANCE,
            Account.TYPE_PEA, Account.TYPE_PERP, Account.TYPE_PER,
        ):
            self.logger.debug('This account is not supported')
            return

        # request to get json is not available yet, old request to get html response
        self.account_details_page.go(params={'idprest': account._prestation_id})

        if account.type in (Account.TYPE_PEA, Account.TYPE_MARKET):
            for invest in self.page.iter_investments(account=account):
                yield invest

        if account.type in (Account.TYPE_LIFE_INSURANCE, Account.TYPE_PERP, Account.TYPE_PER):

            self.auth_life_insurance_api.go()
            self.life_insurance_api.go(id_tech=account._internal_id)

            # Case 1: Life Insurance investment are available on the API.
            if self.page.check_availability():
                self.life_insurance_invest_api.go()
                # Case 2: We need to query a different life insurance space API.
                if not self.page.check_availability():
                    self.life_insurance_invest_api_2.go()
                    investments = self.page.iter_investment()
                    self.life_insurance_invest_details_api.go(id_tech=account._internal_id)
                    for inv in investments:
                        self.page.fill_life_insurance_investment(obj=inv)
                        yield inv
                    return

            # Case 3: Life insurance investments can be parsed on the website.
            else:
                self.account_details_page.go(params={'idprest': account._prestation_id})

                if self.page.has_link():
                    self.life_insurance_invest.go()

            for invest in self.page.iter_investment():
                yield invest

    @need_login
    def access_market_orders(self, account):
        account_dropdown_id = self.page.get_dropdown_menu()
        link = self.page.get_market_order_link()
        if not link:
            self.logger.warning('Could not find Market Order link for account %s.', account.label)
            return
        self.location(link)
        # Once we reached the Market Orders page, we must select the right market account:
        params = {
            'action': '10',
            'numPage': '1',
            'idCptSelect': account_dropdown_id,
        }
        self.market_orders.go(params=params)

    @need_login
    def iter_market_orders(self, account):
        if account.type not in (Account.TYPE_MARKET, Account.TYPE_PEA):
            return

        # Market Orders page sometimes bugs so we try accessing them twice
        for trial in range(2):
            self.account_details_page.go(params={'idprest': account._prestation_id})
            if self.pea_liquidity.is_here():
                self.logger.debug('Liquidity PEA have no market orders')
                return

            self.access_market_orders(account)
            if not self.market_orders.is_here():
                self.logger.warning(
                    'Landed on unknown page when trying to fetch market orders for account %s',
                    account.label
                )
                return

            if self.page.orders_unavailable():
                if trial == 0:
                    self.logger.warning(
                        'Market Orders page is unavailable for account %s, retrying now.',
                        account.label
                    )
                    continue
                self.logger.warning('Market Orders are unavailable for account %s.', account.label)
                return

        if self.page.has_no_market_order():
            self.logger.debug('Account %s has no market orders.', account.label)
            return

        # Handle pagination
        total_pages = self.page.get_pages()
        account_dropdown_id = self.page.get_dropdown_menu()
        for page in range(1, total_pages + 1):
            if page > 1:
                # Select the right page
                params = {
                    'action': '12',
                    'numPage': page,
                    'idCptSelect': account_dropdown_id,
                }
                self.market_orders.go(params=params)
            for order in self.page.iter_market_orders():
                if order.url:
                    self.location(order.url)
                    if self.market_orders_details.is_here():
                        self.page.fill_market_order(obj=order)
                    else:
                        self.logger.warning('Landed on unknown Market Order detail page for order %s', order.label)
                yield order

    @need_login
    def iter_recipients(self, account, ignore_errors=True):
        try:
            self.json_transfer.go()
        except TransferBankError:
            if ignore_errors:
                return []
            raise
        if not self.page.is_able_to_transfer(account):
            return []
        return self.page.iter_recipients(account_id=account.id)

    @need_login
    def init_transfer(self, account, recipient, transfer):
        self.json_transfer.go()

        first_transfer_date = self.page.get_first_available_transfer_date()
        if transfer.exec_date and transfer.exec_date < first_transfer_date:
            transfer.exec_date = first_transfer_date

        self.page.init_transfer(account, recipient, transfer)
        return self.page.handle_response(recipient)

    @need_login
    def execute_transfer(self, transfer):
        assert transfer.id, 'Transfer token is missing'
        data = {
            'b64e200_idVirement': transfer.id,
        }
        # get token and virtual keyboard
        self.sign_transfer.go(params=data)

        data.update(self.page.get_confirm_transfer_data(self.password))
        # execute transfer
        headers = {'Referer': self.absurl('/com/icd-web/vupri/virement.html')}
        self.confirm_transfer.go(data=data, headers=headers)
        assert self.page.is_transfer_validated(), 'Something went wrong, transfer is not executed'

        # return on main page to avoid reload on transfer confirmation page
        self.accounts_main_page.go()
        return transfer

    def end_sms_recipient(self, recipient, **params):
        """End adding recipient with OTP SMS authentication"""
        data = [
            ('context', [self.context, self.context]),
            ('dup', self.dup),
            ('code', params['code']),
            ('csa_op', 'sign'),
        ]
        # needed to confirm recipient validation
        add_recipient_url = self.absurl('/lgn/url.html', base=True)
        self.location(add_recipient_url, data=data, headers={'Referer': add_recipient_url})
        return self.page.get_recipient_object(recipient)

    def end_oob_recipient(self, recipient, **params):
        """End adding recipient with 'pass sécurité' authentication"""
        r = self.open(
            self.absurl('/sec/oob_polling.json'),
            data={'n10_id_transaction': self.id_transaction}
        )
        assert self.id_transaction, "Transaction id is missing, can't sign new recipient."
        r.page.check_recipient_status()

        data = [
            ('context', self.context),
            ('b64_jeton_transaction', self.context),
            ('dup', self.dup),
            ('n10_id_transaction', self.id_transaction),
            ('oob_op', 'sign'),
        ]
        # needed to confirm recipient validation
        add_recipient_url = self.absurl('/lgn/url.html', base=True)
        self.location(add_recipient_url, data=data, headers={'Referer': add_recipient_url})
        return self.page.get_recipient_object(recipient)

    def send_sms_to_user(self, recipient):
        """Add recipient with OTP SMS authentication"""
        data = {}
        data['csa_op'] = 'sign'
        data['context'] = self.context
        self.open(self.absurl('/sec/csa/send.json'), data=data)
        raise AddRecipientStep(
            recipient,
            Value('code', label='Cette opération doit être validée par un Code Sécurité.')
        )

    def send_notif_to_user(self, recipient):
        """Add recipient with 'pass sécurité' authentication"""
        data = {}
        data['b64_jeton_transaction'] = self.context
        r = self.open(self.absurl('/sec/oob_sendoob.json'), data=data)
        self.id_transaction = r.page.get_transaction_id()
        raise AddRecipientStep(recipient, ValueBool('pass', label='Valider cette opération sur votre applicaton société générale'))

    @retry(BrowserUnavailable)
    def get_sign_method(self, data):
        r = self.open(self.absurl('/sec/getsigninfo.json'), data=data)
        return r.page.get_sign_method()

    @need_login
    def new_recipient(self, recipient, **params):
        if 'code' in params:
            return self.end_sms_recipient(recipient, **params)
        if 'pass' in params:
            return self.end_oob_recipient(recipient, **params)

        self.add_recipient.go()
        if self.main_page.is_here():
            self.page.handle_error()
            raise AssertionError('Should not be on this page.')

        self.page.post_iban(recipient)
        self.page.post_label(recipient)

        recipient = self.page.get_recipient_object(recipient, get_info=True)
        self.page.update_browser_recipient_state()
        data = self.page.get_signinfo_data()

        sign_method = self.get_sign_method(data)

        # WARNING: this send validation request to user
        if sign_method == 'CSA':
            return self.send_sms_to_user(recipient)
        elif sign_method == 'OOB':
            return self.send_notif_to_user(recipient)
        raise AssertionError('Sign process unknown: %s' % sign_method)

    @need_login
    def get_advisor(self):
        return self.advisor.go().get_advisor()

    @need_login
    def get_profile(self):
        self.html_profile_page.go()
        return self.page.get_profile()

    @need_login
    def iter_subscription(self):
        self.accounts_main_page.go()
        try:
            profile = self.get_profile()
            subscriber = profile.name
        except (ProfileMissing, BrowserUnavailable):
            subscriber = NotAvailable

        self.accounts.go()
        return self.page.iter_subscription(subscriber=subscriber)

    def _fetch_rib_document(self, subscription):
        d = Document()
        d.id = subscription.id + '_RIB'
        d.url = self.rib_pdf_page.build(params={'b64e200_prestationIdTechnique': subscription._internal_id})
        d.type = DocumentTypes.RIB
        d.format = 'pdf'
        d.label = 'RIB'
        return d

    def _iter_statements(self, subscription):
        # we need _rad_button_id for post_form function
        # if not present it means this subscription doesn't have any bank statement

        end_date = datetime.today()
        begin_date = (end_date - relativedelta(months=+2)).replace(day=1)
        empty_page = 0
        stop_after_empty_limit = 4
        for _ in range(60):
            is_empty = True
            params = {
                'b64e200_prestationIdTechnique': subscription._internal_id,
                'dt10_dateDebut': begin_date.strftime('%d/%m/%Y'),
                'dt10_dateFin': end_date.strftime('%d/%m/%Y'),
            }
            self.documents.go(params=params)
            for d in self.page.iter_documents(subid=subscription.id):
                is_empty = False
                yield d

            if is_empty:
                self.logger.debug('no documents on %s', end_date)
                empty_page += 1

            if empty_page >= stop_after_empty_limit:
                # No more documents
                return

            end_date = begin_date - relativedelta(day=1)
            begin_date = end_date - relativedelta(months=3)

    @need_login
    def iter_documents(self, subscription):
        yield self._fetch_rib_document(subscription)
        for doc in self._iter_statements(subscription):
            yield doc

    @need_login
    def iter_documents_by_types(self, subscription, accepted_types):
        if DocumentTypes.RIB in accepted_types:
            yield self._fetch_rib_document(subscription)

        if DocumentTypes.STATEMENT not in accepted_types:
            return

        for doc in self._iter_statements(subscription):
            yield doc

    @need_login
    def iter_emitters(self):
        try:
            self.json_transfer.go()
        except (TransferBankError, ClientError):
            # some user can't access this page
            return []
        return self.page.iter_emitters()
