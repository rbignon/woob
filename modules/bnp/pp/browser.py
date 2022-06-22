# -*- coding: utf-8 -*-

# Copyright(C) 2009-2016  Romain Bignon
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

from dateutil.relativedelta import relativedelta
from requests.exceptions import ConnectionError

from woob.browser.browsers import LoginBrowser, URL, need_login, StatesMixin
from woob.capabilities.base import find_object
from woob.capabilities.bank import (
    AccountNotFound, Account, AddRecipientStep,
    TransferInvalidRecipient, Loan, AddRecipientBankError,
)
from woob.capabilities.bill import Subscription, Document, DocumentTypes
from woob.capabilities.profile import ProfileMissing
from woob.tools.decorators import retry
from woob.tools.capabilities.bank.bank_transfer import sorted_transfers
from woob.tools.capabilities.bank.transactions import sorted_transactions
from woob.browser.exceptions import ServerError, ClientError, HTTPNotFound
from woob.browser.elements import DataError
from woob.exceptions import (
    BrowserIncorrectPassword, BrowserUnavailable, AppValidation,
    AppValidationExpired, ActionNeeded, ActionType, BrowserUserBanned, BrowserPasswordExpired,
)
from woob.tools.value import Value
from woob.tools.capabilities.bank.investments import create_french_liquidity
from woob.browser.filters.standard import QueryValue

from .pages import (
    LoginPage, AccountsPage, AccountsIBANPage, HistoryPage, TransferInitPage,
    ConnectionThresholdPage, LifeInsurancesPage, LifeInsurancesHistoryPage,
    LifeInsurancesDetailPage, NatioVieProPage, CapitalisationPage, MarketOrdersPage,
    MarketListPage, MarketPage, MarketHistoryPage, MarketSynPage, BNPKeyboard,
    RecipientsPage, ValidateTransferPage, RegisterTransferPage, AdvisorPage,
    AddRecipPage, ActivateRecipPage, ProfilePage, ListDetailCardPage, ListErrorPage,
    UselessPage, TransferAssertionError, LoanDetailsPage, TransfersPage, OTPPage,
    UnavailablePage, InitLoginPage, FinalizeLoginPage, InfoClientPage,
    StatusPage,
)
from .document_pages import DocumentsPage, TitulairePage, RIBPage


__all__ = ['BNPPartPro', 'HelloBank']


class BNPParibasBrowser(LoginBrowser, StatesMixin):
    TIMEOUT = 30.0

    init_login = URL(r'/auth/login', InitLoginPage)

    auth_status = URL(r'/auth/status', StatusPage)

    info_client = URL(
        r'/serviceinfosclient-wspl/rpc/InfosClient\?modeAppel=0',
        InfoClientPage
    )

    login = URL(
        r'https://connexion-mabanque.bnpparibas/login',
        LoginPage
    )

    finalize_login = URL(
        r'SEEA-pa01/devServer/seeaserver',
        FinalizeLoginPage
    )

    errors_list = URL(
        r'/rsc/contrib/identification/src/zonespubliables/mabanque-part/fr/identification-fr-part-CAS.json',
        ListErrorPage
    )

    list_error_page = URL(
        r'https://mabanque.bnpparibas/rsc/contrib/document/properties/identification-fr-part-V1.json', ListErrorPage
    )

    useless_page = URL(
        r'https://.*/fr/secure/comptes-et-contrats',
        UselessPage
    )

    otp = URL(
        r'/fr/espace-prive/authentification-forte-anr',
        r'https://.*/fr/secure/authentification-forte',  # We can be redirected on other baseurl
        OTPPage
    )

    con_threshold = URL(
        r'https://.*/100-connexion',
        r'/fr/connexion/mot-de-passe-expire',
        r'/fr/secure/mot-de-passe-expire',
        r'/fr/espace-pro/changer-son-mot-de-passe',
        r'/fr/espace-prive/mot-de-passe-expire',
        r'/fr/client/mdp-expire',
        ConnectionThresholdPage
    )
    unavailable_page = URL(
        r'/fr/systeme/page-indisponible',
        UnavailablePage
    )
    accounts = URL(r'udc-wspl/rest/getlstcpt', AccountsPage)
    loan_details = URL(r'caraccomptes-wspl/rpc/(?P<loan_type>.*)', LoanDetailsPage)
    ibans = URL(r'rib-wspl/rpc/comptes', AccountsIBANPage)
    history = URL(r'rop2-wspl/rest/releveOp', HistoryPage)
    history_old = URL(r'rop-wspl/rest/releveOp', HistoryPage)
    transfer_init = URL(r'virement-wspl/rest/initialisationVirement', TransferInitPage)
    transfer_history = URL(r'virement-wspl/rest/historiqueVirementIP', TransfersPage)

    lifeinsurances = URL(r'mefav-wspl/rest/infosContrat', LifeInsurancesPage)
    lifeinsurances_history = URL(r'mefav-wspl/rest/listMouvements', LifeInsurancesHistoryPage)
    lifeinsurances_detail = URL(r'mefav-wspl/rest/detailMouvement', LifeInsurancesDetailPage)

    natio_vie_pro = URL(r'/mefav-wspl/rest/natioViePro', NatioVieProPage)
    capitalisation_page = URL(
        r'https://www.clients.assurance-vie.fr/servlets/helios.cinrj.htmlnav.runtime.FrontServlet',
        CapitalisationPage,
    )

    market_list = URL(r'pe-war/rpc/SAVaccountDetails/get', MarketListPage)
    market_syn = URL(r'pe-war/rpc/synthesis/get', MarketSynPage)
    market = URL(r'pe-war/rpc/portfolioDetails/get', MarketPage)
    market_history = URL(r'/pe-war/rpc/turnOverHistory/get', MarketHistoryPage)
    market_orders = URL(r'/pe-war/rpc/orderDetailList/get', MarketOrdersPage)

    recipients = URL(r'/virement-wspl/rest/listerBeneficiaire', RecipientsPage)
    add_recip = URL(r'/virement-wspl/rest/ajouterBeneficiaire', AddRecipPage)
    activate_recip_sms = URL(r'/virement-wspl/rest/activerBeneficiaire', ActivateRecipPage)
    activate_recip_digital_key = URL(r'/virement-wspl/rest/verifierAuthentForte', ActivateRecipPage)
    request_recip_activation = URL(r'/virement-wspl/rest/demanderCodeActivation', AddRecipPage)
    validate_transfer = URL(r'/virement-wspl/rest/validationVirementIP', ValidateTransferPage)
    register_transfer = URL(r'/virement-wspl/rest/enregistrerVirement', RegisterTransferPage)

    advisor = URL(r'/conseiller-wspl/rest/monConseiller', AdvisorPage)

    titulaire = URL(r'/demat-wspl/rest/listerTitulairesDemat', TitulairePage)
    document = URL(r'/demat-wspl/rest/listerDocuments', DocumentsPage)
    document_research = URL(r'/demat-wspl/rest/modificationTitulaireConsultationDemat', DocumentsPage)
    rib_page = URL(r'/rib-wspl/rpc/restituerRIB', RIBPage)

    profile = URL(r'/kyc-wspl/rest/informationsClient', ProfilePage)
    list_detail_card = URL(r'/udcarte-wspl/rest/listeDetailCartes', ListDetailCardPage)

    DIST_ID = None

    STATE_DURATION = 10

    __states__ = ('rcpt_transfer_id',)

    def __init__(self, config, *args, **kwargs):
        super(BNPParibasBrowser, self).__init__(config['login'].get(), config['password'].get(), *args, **kwargs)
        self.accounts_list = None
        self.card_to_transaction_type = {}
        self.rotating_password = config['rotating_password'].get()
        self.digital_key = config['digital_key'].get()
        self.rcpt_transfer_id = None

    @retry(ConnectionError, tries=3)
    def open(self, *args, **kwargs):
        return super(BNPParibasBrowser, self).open(*args, **kwargs)

    def check_redirections(self):
        # We must check each request one by one to check if an otp will be sent after the redirections
        # We can have 14 redirections in a row from what we saw, so we set the range to 20 just in case.
        for _ in range(20):  # To avoid infinite redirections
            next_location = self.response.headers.get('location')
            if not next_location:
                break

            # This is temporary while we handle the new change pass
            if self.con_threshold.is_here():
                raise BrowserPasswordExpired()

            self.location(next_location, allow_redirects=False)
            if self.otp.is_here():
                raise ActionNeeded(
                    locale="fr-FR", message="Veuillez réaliser l'authentification forte depuis votre navigateur.",
                    action_type=ActionType.PERFORM_MFA,
                )

            # For some errors, bnp doesn't return a 403 but redirect to the login page with an error message
            # Instead of following the redirection, we parse the errorCode and raise exception with accurate error message
            error_code = QueryValue(None, 'errorCode', default=None).filter(
                self.response.headers.get('location', '')
            )
            if error_code:
                self.list_error_page.go()
                error_message = self.page.get_error_message(error_code)
                raise BrowserUnavailable(error_message)
        else:
            raise AssertionError('Unknown redirection behavior')

    def do_login(self):
        if not (self.username.isdigit() and self.password.isdigit()):
            raise BrowserIncorrectPassword()

        self.info_client.go()
        assert self.info_client.is_here()
        if self.page.logged:
            return

        self.init_login.go()

        if self.login.is_here():
            try:
                # Redirection process does all the login by itself but we must
                # stop it to manually check if there's an OTP or any error
                self.page.login(self.username, self.password)
                self.check_redirections()
            except ClientError as e:
                error = LoginPage(self, e.response).get_error()
                self.errors_list.go()
                error_message = self.page.get_error_message(error)
                raise self.get_exception_from_message(error, error_message)

        # Even if we checked just above for exceptions, it seems that some error cases, such as inputting bnp creds on
        # hello bank, still return a 200, at this point we only check that we are back on login page
        if self.login.is_here():
            raise BrowserIncorrectPassword()

    def get_exception_from_message(self, message, error_message):

        map_exception_to_messages = {
            BrowserIncorrectPassword: {
                'authenticationFailure.ClientNotFoundException201',
                'authenticationFailure.SecretErrorException201',
                'authenticationFailure.CompletedS1ErrorSecretException18',
                'authenticationFailure.CompletedS2ErrorSecretException19',
                'authenticationFailure.FailedLoginException',
                'authenticationFailure.ZosConnectGetIKPIException',
                'authenticationFailure.CasInvalidCredentialSecurityAttributeException',
            },
            BrowserUserBanned: {
                'authenticationFailure.CurrentS1DelayException3',
                'authenticationFailure.CurrentS2DelayException4',
                'authenticationFailure.LockedAccountException202',
            },
            BrowserUnavailable: {
                'authenticationFailure.TechnicalException900',
                'authenticationFailure.TechnicalException917',
                'authenticationFailure.TechnicalException901',
                'authenticationFailure.TechnicalException902',
                'authenticationFailure.TechnicalException903',
                'authenticationFailure.TechnicalException904',
                'authenticationFailure.TechnicalException905',
            },
            BrowserPasswordExpired: {
                'authenticationFailure.ExpiredTmpPwdException50',
            },
        }

        for exception, messages in map_exception_to_messages.items():
            if message in messages:
                return exception(error_message)
        else:
            return AssertionError('Unhandled error at login: %s: %s' % (message, error_message))

    def load_state(self, state):
        # reload state only for new recipient feature
        if state.get('rcpt_transfer_id'):
            state.pop('url', None)
            super(BNPParibasBrowser, self).load_state(state)

    def change_pass(self, oldpass, newpass):
        res = self.open('/mcs-wspl/rpc/grille?accessible=false')
        url = '/mcs-wspl/rpc/grille/%s' % res.json()['data']['idGrille']
        keyboard = self.open(url)
        vk = BNPKeyboard(self, keyboard)
        data = {}
        data['codeAppli'] = 'PORTAIL'
        data['idGrille'] = res.json()['data']['idGrille']
        data['typeGrille'] = res.json()['data']['typeGrille']
        data['confirmNouveauPassword'] = vk.get_string_code(newpass)
        data['nouveauPassword'] = vk.get_string_code(newpass)
        data['passwordActuel'] = vk.get_string_code(oldpass)
        response = self.location('/mcs-wspl/rpc/modifiercodesecret', data=data)
        statut = response.json().get('statut')
        self.logger.warning('Password change response : statut="%s" - message="%s"', statut, response.json().get('messageIden'))
        if statut != '1':
            return False
        self.location('/mcs-wspl/rpc/validercodesecret')
        return True

    @need_login
    def get_profile(self):
        self.profile.go(json={})
        profile = self.page.get_profile()
        if profile:
            return profile
        raise ProfileMissing(self.page.get_error_message())

    def is_loan(self, account):
        return account.type in (
            Account.TYPE_LOAN, Account.TYPE_MORTGAGE, Account.TYPE_CONSUMER_CREDIT, Account.TYPE_REVOLVING_CREDIT,
        )

    @need_login
    def iter_accounts(self):
        if self.accounts_list is None:
            self.accounts_list = []
            # In case of password renewal, we need to go on ibans twice.
            self.ibans.go()
            if not self.ibans.is_here():
                self.ibans.go()

            if self.otp.is_here():
                raise ActionNeeded(
                    locale="fr-FR", message="Veuillez réaliser l'authentification forte depuis votre navigateur.",
                    action_type=ActionType.PERFORM_MFA,
                )

            ibans = self.page.get_ibans_dict()
            is_pro = {}
            # This page might be unavailable.
            try:
                self.transfer_init.go(json={'modeBeneficiaire': '0'})
                ibans.update(self.page.get_ibans_dict('Crediteur'))
                is_pro = self.page.get_pro_accounts('Crediteur')
            except (TransferAssertionError, AttributeError):
                pass

            self.accounts.go()
            accounts = list(self.page.iter_accounts(
                ibans=ibans,
                is_pro=is_pro,
            ))
            self.market_syn.go(json={})
            market_accounts = self.page.get_list()  # get the list of 'Comptes Titres'
            checked_accounts = set()
            for account in accounts:
                if self.is_loan(account):
                    account = Loan.from_dict(account.to_dict())
                    if account.type in (Account.TYPE_MORTGAGE, Account.TYPE_CONSUMER_CREDIT):
                        self.loan_details.go(data={'iban': account.id}, loan_type='creditPret')
                        self.page.fill_loan_details(obj=account)

                    elif account.type == Account.TYPE_REVOLVING_CREDIT:
                        self.loan_details.go(data={'iban': account.id}, loan_type='creditConsoProvisio')
                        self.page.fill_revolving_details(obj=account)

                    elif account.type == Account.TYPE_LOAN:
                        self.loan_details.go(data={'iban': account.id}, loan_type='creditPretPersoPro')
                        self.page.fill_loan_details(obj=account)

                for market_acc in market_accounts:
                    if all((
                        market_acc['securityAccountNumber'].endswith(account.number[-4:]),
                        account.type in (Account.TYPE_MARKET, Account.TYPE_PEA),
                        account.label == market_acc['securityAccountName'],
                        not account.iban,
                    )):
                        if account.id in checked_accounts:
                            # in this case, we have identified two accounts for the same CompteTitre
                            raise DataError('we have two market accounts mapped to a same "CompteTitre" dictionary')

                        checked_accounts.add(account.id)
                        account.balance = market_acc.get('valorisation', account.balance)
                        account.valuation_diff = market_acc['profitLoss']
                        break
                self.accounts_list.append(account)

            # Fetching capitalisation contracts from the "Assurances Vie" space (some are not in the BNP API):
            self.natio_vie_pro.go()
            message = self.page.get_life_insurance_unavailable_message()

            # It seems that natio_vie_pro can return an error message and from that we are not able to make
            # requests on the natio insurance life space.
            if message != 'OK':
                # "Probleme lors du cryptage des DAT" is the main error returned
                # To keep under watch if there is changes about this spaces
                self.logger.warning("Natio life insurance space is unavailable : " + message)
            else:
                params = self.page.get_params()

                try:
                    # When the space does not exist we land on a 302 that tries to redirect
                    # to an unexisting domain, hence the 'allow_redirects=False'.
                    # Sometimes the Life Insurance space is unavailable, hence the 'ConnectionError'.
                    self.location(self.capitalisation_page.build(params=params), allow_redirects=False)
                except (ServerError, ConnectionError):
                    self.logger.warning("An Internal Server Error occurred")
                except HTTPNotFound:
                    self.logger.warning('capitalisation_page not found')
                    pass
                else:
                    if self.capitalisation_page.is_here() and self.page.has_contracts():
                        for account in self.page.iter_capitalisation():
                            # Life Insurance accounts may appear BOTH in the API and the "Assurances Vie" domain,
                            # It is better to keep the API version since it contains the unitvalue:
                            if account.number not in [a.number for a in self.accounts_list]:
                                self.logger.warning("We found an account that only appears on the old BNP website.")
                                self.accounts_list.append(account)
                            else:
                                self.logger.warning("This account was skipped because it already appears in the API.")

        return iter(self.accounts_list)

    def get_account(self, _id):
        return find_object(self.iter_accounts(), id=_id, error=AccountNotFound)

    @need_login
    def iter_history(self, account, coming=False):
        # The accounts from the "Assurances Vie" space have no available history:
        if hasattr(account, '_details'):
            return []
        if account.type == Account.TYPE_PEA and account.label.endswith('Espèces'):
            return []
        if account.type == Account.TYPE_LIFE_INSURANCE:
            return self.iter_lifeinsurance_history(account, coming)
        elif account.type in (Account.TYPE_MARKET, Account.TYPE_PEA):
            if coming:
                return []
            try:
                self.market_list.go(json={})
            except ServerError:
                self.logger.warning("An Internal Server Error occurred")
                return []
            for market_acc in self.page.get_list():
                if account.number[-4:] == market_acc['securityAccountNumber'][-4:]:
                    self.page = self.market_history.go(
                        json={
                            "securityAccountNumber": market_acc['securityAccountNumber'],
                        }
                    )
                    return self.page.iter_history()
            return []
        else:
            if not self.card_to_transaction_type:
                self.list_detail_card.go()
                self.card_to_transaction_type = self.page.get_card_to_transaction_type()
            data = {
                "ibanCrypte": account.id,
                "pastOrPending": 1,
                "triAV": 0,
                "startDate": (datetime.now() - relativedelta(years=1)).strftime('%d%m%Y'),
                "endDate": datetime.now().strftime('%d%m%Y'),
            }
            try:
                self.history.go(json=data)
            except BrowserUnavailable:
                # old url is still used for certain connections bu we don't know which one is,
                # so the same HistoryPage is attained by the old url in another URL object
                data['startDate'] = (datetime.now() - relativedelta(years=3)).strftime('%d%m%Y')
                # old url authorizes up to 3 years of history
                self.history_old.go(data=data)

            if coming:
                return sorted_transactions(self.page.iter_coming())
            else:
                return sorted_transactions(self.page.iter_history())

    @need_login
    def iter_lifeinsurance_history(self, account, coming=False):
        self.lifeinsurances_history.go(json={
            "ibanCrypte": account.id,
        })

        for tr in self.page.iter_history(coming):
            page = self.lifeinsurances_detail.go(
                json={
                    "ibanCrypte": account.id,
                    "idMouvement": tr._op.get('idMouvement'),
                    "ordreMouvement": tr._op.get('ordreMouvement'),
                    "codeTypeMouvement": tr._op.get('codeTypeMouvement'),
                }
            )
            tr.investments = list(page.iter_investments())
            yield tr

    @need_login
    def iter_coming_operations(self, account):
        return self.iter_history(account, coming=True)

    @need_login
    def iter_investment(self, account):
        if account.type == Account.TYPE_PEA and 'espèces' in account.label.lower():
            return [create_french_liquidity(account.balance)]

        # Life insurances and PERP may be scraped from the API or from the "Assurance Vie" space,
        # so we need to discriminate between both using account._details:
        if account.type in (
            account.TYPE_LIFE_INSURANCE,
            account.TYPE_PERP,
            account.TYPE_CAPITALISATION,
            account.TYPE_PER,
        ):
            if hasattr(account, '_details'):
                # Going to the "Assurances Vie" page
                natiovie_params = self.natio_vie_pro.go().get_params()
                self.capitalisation_page.go(params=natiovie_params)
                # Fetching the form to get the contract investments:
                capitalisation_params = self.page.get_params(account)
                self.capitalisation_page.go(params=capitalisation_params)
                return self.page.iter_investments()
            else:
                # No capitalisation contract has yet been found in the API:
                assert account.type != account.TYPE_CAPITALISATION
                self.lifeinsurances.go(json={
                    "ibanCrypte": account.id,
                })
                return self.page.iter_investments()

        elif account.type in (account.TYPE_MARKET, account.TYPE_PEA):
            try:
                self.market_list.go(json={})
            except ServerError:
                self.logger.warning("An Internal Server Error occurred")
                return []
            for market_acc in self.page.get_list():
                if account.number[-4:] == market_acc['securityAccountNumber'][-4:] and not account.iban:
                    try:
                        # Sometimes generates an Internal Server Error ...
                        self.market.go(json={
                            "securityAccountNumber": market_acc['securityAccountNumber'],
                        })
                    except ServerError:
                        self.logger.warning("An Internal Server Error occurred")
                        break
                    return self.page.iter_investments()

        return []

    @need_login
    def iter_market_orders(self, account):
        if (
            account.type not in (Account.TYPE_MARKET, account.TYPE_PEA)
            or 'espèces' in account.label.lower()
        ):
            return []

        try:
            self.market_list.go(json={})
        except ServerError:
            self.logger.warning('An Internal Server Error occurred')
            return []

        for market_acc in self.page.get_list():
            if account.number[-4:] == market_acc['securityAccountNumber'][-4:] and not account.iban:
                json = {
                    'securityAccountNumber': market_acc['securityAccountNumber'],
                    'filterCriteria': [],
                    'sortColumn': 'orderDateTransmission',
                    'sortType': 'desc',
                }
                try:
                    # Sometimes generates an Internal Server Error ...
                    self.market_orders.go(json=json)
                except ServerError:
                    self.logger.warning('An Internal Server Error occurred')
                    break
                return self.page.iter_market_orders()

        # In case we haven't found the account with get_list
        return []

    @need_login
    def iter_recipients(self, origin_account_id):
        try:
            if (
                origin_account_id not in self.transfer_init.go(json={
                    'modeBeneficiaire': '0',
                }).get_ibans_dict('Debiteur')
            ):
                raise NotImplementedError()
        except TransferAssertionError:
            return

        # avoid recipient with same iban
        seen = set()
        for recipient in self.page.transferable_on(origin_account_ibancrypte=origin_account_id):
            if recipient.iban not in seen:
                seen.add(recipient.iban)
                yield recipient

        if self.page.can_transfer_to_recipients(origin_account_id):
            for recipient in self.recipients.go(json={'type': 'TOUS'}).iter_recipients():
                if recipient.iban not in seen:
                    seen.add(recipient.iban)
                    yield recipient

    @need_login
    def new_recipient(self, recipient, **params):
        if 'code' in params:
            # for sms authentication
            return self.send_code(recipient, **params)

        # prepare commun data for all authentication method
        data = {
            'adresseBeneficiaire': '',
            'iban': recipient.iban,
            'libelleBeneficiaire': recipient.label,
            'notification': True,
            'typeBeneficiaire': '',
        }

        # provisional
        if self.digital_key and 'resume' in params:
            return self.new_recipient_digital_key(recipient, data)

        # Reset any existing rcpt_transfer_id when adding a new recipient
        self.rcpt_transfer_id = None

        # need to be on recipient page send sms or mobile notification
        # needed to get the phone number, enabling the possibility to send sms.
        # all users with validated phone number can receive sms code
        self.recipients.go(json={'type': 'TOUS'})

        assert self.recipients.is_here(), 'Not on the expected recipient page'

        # check type of recipient activation
        type_activation = 'sms'

        # provisional
        if self.digital_key:
            if self.page.has_digital_key():
                # force users with digital key activated to use digital key authentication
                type_activation = 'digital_key'

        existing_rcpt = None
        for rcpt in self.page.iter_recipients():
            if rcpt.iban == recipient.iban:
                existing_rcpt = rcpt
                break

        if existing_rcpt:
            # There was already an existing recipient with this iban
            if existing_rcpt._web_state != 'En attente':
                raise AddRecipientBankError(message="Un bénéficiaire avec le même iban est déjà présent")

            if existing_rcpt.label != recipient.label:
                raise AddRecipientBankError(
                    message="Un bénéficiaire avec le même iban et un label différent est attente d'activation sur le site de la banque"
                )

            activation_data = {
                'typeEnvoi': 'SMS',
                'notification': True,
                'idBeneficiaire': existing_rcpt._raw_id,
            }

        if type_activation == 'sms':
            if existing_rcpt:
                # Send activation request for an existing recipient
                self.request_recip_activation.go(json=activation_data)
            else:
                # post recipient data sending sms with same request
                data['typeEnvoi'] = 'SMS'
                self.add_recip.go(json=data)
            recipient = self.page.get_recipient(recipient)
            self.rcpt_transfer_id = recipient._raw_id

            raise AddRecipientStep(recipient, Value('code', label='Saisissez le code reçu par SMS.'))

        if type_activation == 'digital_key':
            # recipient validated with digital key are immediatly available
            recipient.enabled_at = datetime.today()
            if existing_rcpt:
                self.rcpt_transfer_id = existing_rcpt._raw_id
            raise AppValidation(
                resource=recipient,
                message='Veuillez valider le bénéficiaire sur votre application mobile bancaire.',
            )

        raise AssertionError('Unhandled activation type: "%s"' % type_activation)

    @need_login
    def send_code(self, recipient, **params):
        """Add recipient with sms otp authentication"""
        if not self.rcpt_transfer_id:
            raise AddRecipientBankError(message="Aucun code SMS n'est attendu. Le code est peut être expiré.")

        data = {
            'idBeneficiaire': self.rcpt_transfer_id,
            'typeActivation': 1,
            'codeActivation': params['code'],
        }
        self.activate_recip_sms.go(json=data)
        # Clear the rcpt_transfer_id only if the activation was successful
        self.rcpt_transfer_id = None
        return self.page.get_recipient(recipient)

    @need_login
    def new_recipient_digital_key(self, recipient, data):
        """Add recipient with 'clé digitale' authentication"""
        if self.rcpt_transfer_id:
            # Activate an already existing recipient:
            activation_data = {
                'typeEnvoi': 'AF',
                'notification': True,
                'idBeneficiaire': self.rcpt_transfer_id,
            }
            self.request_recip_activation.go(json=activation_data)
        else:
            # Post recipient data, sending app notification with same request
            data['typeEnvoi'] = 'AF'
            self.add_recip.go(json=data)
        recipient = self.page.get_recipient(recipient)

        # prepare data for polling
        assert recipient._id_transaction
        polling_data = {
            'idBeneficiaire': recipient._raw_id,
            'typeActivation': 2,
            'idTransaction': recipient._id_transaction,
        }

        # float(second), 5 min like bnp website
        timeout = time.time() + 300.00

        # polling
        while time.time() < timeout:
            time.sleep(5)  # like website
            self.activate_recip_digital_key.go(json=polling_data)
            if self.page.is_recipient_validated():
                break
        else:
            raise AppValidationExpired()

        # Clear the rcpt_transfer_id only if the activation was successful
        self.rcpt_transfer_id = None
        return recipient

    @need_login
    def prepare_transfer(self, account, recipient, amount, reason, exec_date):
        data = {}
        data['devise'] = account.currency
        data['motif'] = reason
        data['dateExecution'] = exec_date.strftime('%d-%m-%Y')
        data['compteDebiteur'] = account.id
        data['montant'] = str(amount)
        data['typeVirement'] = 'SEPA'
        if recipient.category == u'Externe':
            data['idBeneficiaire'] = recipient._raw_id
        else:
            data['compteCrediteur'] = recipient.id
        return data

    @need_login
    def prepare_transfer_execution(self, transfer):
        assert hasattr(transfer, '_type_operation'), 'Transfer obj attribute _type_operation is missing'
        assert hasattr(transfer, '_repartition_frais'), 'Transfer obj attribute _repartition_frais is missing'

        data = {
            'emailBeneficiaire': '',
            'mode': '2',
            'notification': True,
            'referenceVirement': transfer.id,
            'typeOperation': transfer._type_operation,
            'typeRepartitionFrais': transfer._repartition_frais,
        }
        return data

    @need_login
    def init_transfer(self, account, recipient, amount, reason, exec_date):
        if recipient._web_state == 'En attente':
            raise TransferInvalidRecipient(message="Le bénéficiaire sélectionné n'est pas activé")

        data = self.prepare_transfer(account, recipient, amount, reason, exec_date)
        return self.validate_transfer.go(json=data).handle_response(account, recipient, amount, reason)

    @need_login
    def execute_transfer(self, transfer):
        data = self.prepare_transfer_execution(transfer)
        self.register_transfer.go(json=data)
        return self.page.handle_response(transfer)

    @need_login
    def get_advisor(self):
        self.advisor.stay_or_go()
        if self.page.has_error():
            return None
        return self.page.get_advisor()

    @need_login
    def iter_threads(self):
        raise NotImplementedError()

    @need_login
    def get_thread(self, thread):
        raise NotImplementedError()

    @need_login
    def iter_subscription(self):
        acc_list = self.iter_accounts()

        for acc in acc_list:
            sub = Subscription()
            sub.label = acc.label
            sub.subscriber = acc._subscriber
            sub.id = acc.id
            # number is the hidden number of an account like "****1234"
            # and it's used in the parsing of the docs in iter_documents
            sub._number = acc.number
            # iduser is the ikpi affiliate to the account,
            # usefull for multi titulaires connexions
            sub._iduser = acc._iduser
            yield sub

    @need_login
    def iter_emitters(self):
        self.transfer_init.go(json={'modeBeneficiaire': '0'})
        return self.page.iter_emitters()

    @need_login
    def iter_transfers(self, account):
        self.transfer_history.go(method='POST')
        for tr in sorted_transfers(self.page.iter_transfers()):
            if not account or account.iban == tr.account_iban:
                yield tr


class BNPPartPro(BNPParibasBrowser):
    BASEURL_TEMPLATE = r'https://%s.bnpparibas/'
    BASEURL = BASEURL_TEMPLATE % 'mabanque'
    # BNPNetEntrepros is supposed to be for pro accounts, but it seems that BNPNetParticulier
    # works for pros as well, on the other side BNPNetEntrepros doesn't work for part
    DIST_ID = 'BNPNetParticulier'

    def __init__(self, config=None, *args, **kwargs):
        self.config = config
        super(BNPPartPro, self).__init__(self.config, *args, **kwargs)

    def switch(self, subdomain):
        self.BASEURL = self.BASEURL_TEMPLATE % subdomain

    def _fetch_rib_document(self, subscription):
        self.rib_page.go(
            params={
                'contractId': subscription.id,
                'i18nSiteType': 'part',  # site type value doesn't seem to matter as long as it's present
                'i18nLang': 'fr',
                'i18nVersion': 'V1',
            },
        )
        if self.rib_page.is_here() and self.page.is_rib_available():
            d = Document()
            d.id = subscription.id + '_RIB'
            d.url = self.page.url
            d.type = DocumentTypes.RIB
            d.format = 'pdf'
            d.label = 'RIB'
            return d

    @need_login
    def iter_documents(self, subscription):
        rib = self._fetch_rib_document(subscription)
        if rib:
            yield rib

        docs = []
        id_docs = []

        # Those 2 requests are needed or we get an error when going on document_research
        self.titulaire.go()
        self.document.go()

        data = {
            'numCompte': subscription._number,
        }
        self.document_research.go(json=data)
        if self.page.has_error():
            return

        iter_documents_functions = [self.page.iter_documents_pro, self.page.iter_documents]
        for iter_documents in iter_documents_functions:
            for doc in iter_documents(
                sub_id=subscription.id, sub_number=subscription._number, baseurl=self.BASEURL
            ):
                if doc.id not in id_docs:
                    docs.append(doc)
                    id_docs.append(doc.id)

        # documents are sorted by type then date, sort them directly by date
        docs = sorted(docs, key=lambda doc: doc.date, reverse=True)
        for doc in docs:
            yield doc


class HelloBank(BNPParibasBrowser):
    BASEURL = 'https://www.hellobank.fr/'
    DIST_ID = 'HelloBank'

    init_login = URL(
        r'/auth/login',
        InitLoginPage
    )
    login = URL(
        r'https://espace-client.hellobank.fr/login',
        LoginPage
    )
    errors_list = URL(
        r'/rsc/contrib/identification/src/zonespubliables/hellobank/fr/identification-fr-hellobank-CAS.json',
        ListErrorPage
    )

    def _fetch_rib_document(self, subscription):
        self.rib_page.go(
            params={
                'contractId': subscription.id,
                'i18nSiteType': 'part',  # site type value doesn't seem to matter as long as it's present
                'i18nLang': 'fr',
                'i18nVersion': 'V1',
            },
        )
        if self.rib_page.is_here() and self.page.is_rib_available():
            d = Document()
            d.id = subscription.id + '_RIB'
            d.url = self.page.url
            d.type = DocumentTypes.RIB
            d.format = 'pdf'
            d.label = 'RIB'
            return d

    @need_login
    def iter_documents(self, subscription):
        rib = self._fetch_rib_document(subscription)
        if rib:
            yield rib
