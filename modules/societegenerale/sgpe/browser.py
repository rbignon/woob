# -*- coding: utf-8 -*-

# Copyright(C) 2013-2021      Romain Bignon
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

from datetime import date
from base64 import b64encode
from urllib.parse import quote_plus

from dateutil.relativedelta import relativedelta

from woob.browser.browsers import need_login
from woob.browser.url import URL
from woob.browser.exceptions import ClientError
from woob.capabilities.base import find_object
from woob.capabilities.bank import (
    RecipientNotFound, AddRecipientStep, AddRecipientBankError,
    Recipient, TransferBankError, AccountOwnerType,
)
from woob.exceptions import (
    BrowserPasswordExpired, BrowserUnavailable, NoAccountsException,
)
from woob.tools.decorators import retry
from woob.tools.value import Value
from woob.tools.json import json

from .pages import (
    ChangePassPage, InscriptionPage, ErrorPage, MarketAccountsDetailsPage, MarketAccountsPage, UselessPage,
    MainPage, MainPEPage, LoginPEPage, UnavailablePage,
)
from .json_pages import (
    AccountsJsonPage, BalancesJsonPage, CorpListPage, HistoryJsonPage, BankStatementPage,
    MarketAccountPage, MarketInvestmentPage, ProLoanDetailsPage, ProLoansPage, WealthAccountsPage, ProfilePEPage,
    DeferredCardJsonPage, DeferredCardHistoryJsonPage, CardsInformationPage, CardsInformation2Page,
)
from .transfer_pages import (
    EasyTransferPage, RecipientsJsonPage, TransferPage, SignTransferPage, TransferDatesPage,
    AddRecipientPage, AddRecipientStepPage, ConfirmRecipientPage, ConfirmTransferPage,
)
from ..browser import SocieteGeneraleTwoFactorBrowser as SocieteGeneraleLogin


__all__ = ['SGProfessionalBrowser', 'SGEnterpriseBrowser']


class SGPEBrowser(SocieteGeneraleLogin):
    login = URL(
        r'/sec/vk/authent.json',
        r'/sec/oob_sendooba.json',
        r'/sec/oob_pollingooba.json',
        r'/sec/oob_auth.json',
        r'/sec/csa/send.json',
        r'/sec/csa/check.json',
        LoginPEPage
    )

    accounts_main_page = URL(r'/icd-web/syd-front/index-comptes.html', MainPage)
    accounts = URL('/icd/syd-front/data/syd-comptes-accederDepuisMenu.json', AccountsJsonPage)
    intraday_accounts = URL('/icd/syd-front/data/syd-intraday-accederDepuisMenu.json', AccountsJsonPage)
    balances = URL('/icd/syd-front/data/syd-comptes-chargerSoldes.json', BalancesJsonPage)
    intraday_balances = URL('/icd/syd-front/data/syd-intraday-chargerSoldes.json', BalancesJsonPage)

    history = URL(
        '/icd/syd-front/data/syd-comptes-chargerReleve.json',
        '/icd/syd-front/data/syd-intraday-chargerDetail.json',
        HistoryJsonPage
    )
    history_next = URL('/icd/syd-front/data/syd-comptes-chargerProchainLotEcriture.json', HistoryJsonPage)

    profile = URL(r'/icd/gax/data/users/authenticated-user.json', ProfilePEPage)

    deferred_card_history = URL(
        '/icd/npe/data/operationFuture/getDetailCarteAVenir-authsec.json', DeferredCardHistoryJsonPage
    )
    cards_information = URL('/icd/crtes/data/crtes-all-pms.json', CardsInformationPage)
    cards_information2 = URL(
        '/icd/npe/data/operationFuture/getListeDesCartesAvecOperationsAVenir-authsec.json', CardsInformation2Page
    )
    deferred_card = URL(
        r'/icd/crtes/data/crtes-carte-for-pm.json\?an200_idPPouPM=(?P<card_id>\w+)', DeferredCardJsonPage
    )

    change_pass = URL(
        '/gao/changer-code-secret-expire-saisie.html',
        '/gao/changer-code-secret-inscr-saisie.html',
        '/gao/inscrire-utilisateur-saisie.html',
        '/gao/changer-code-secret-reattr-saisie.html',
        '/gae/afficherInscriptionUtilisateur.html',
        '/gae/afficherChangementCodeSecretExpire.html',
        ChangePassPage
    )
    inscription_page = URL('/icd-web/gax/gax-inscription-utilisateur.html', InscriptionPage)

    @need_login
    def get_accounts_list(self):
        # 'Comptes' are standard accounts on sgpe website
        # 'Opérations du jour' are intraday accounts on sgpe website
        # Standard and Intraday accounts are same accounts with different detail
        # User could have standard accounts with no intraday accounts or the contrary
        # They also could have both, in that case, retrieve only standard accounts
        try:
            # get standard accounts
            self.accounts.go()
            self.page.check_error()
            accounts = list(self.page.iter_class_accounts())
            self.balances.go()
        except NoAccountsException:
            # get intraday accounts
            self.intraday_accounts.go()
            accounts = list(self.page.iter_class_accounts())
            self.intraday_balances.go()

        for acc in self.page.populate_balances(accounts):
            acc._bisoftcap = {'deferred_cb': {'softcap_day': 1000, 'day_for_softcap': 5, 'date_field': 'rdate'}}
            acc.owner_type = AccountOwnerType.ORGANIZATION
            yield acc

        # try to get deferred cards if any
        self.cards_information.go()
        # If NOK is responded, then there is no card on this account
        if self.page.response.json()['commun']['statut'] == "OK":
            for account in self.page.response.json()['donnees']:
                card_id = account['idPPouPM']
                self.deferred_card.go(card_id=card_id)
                if self.page.response.json()['commun']['statut'] == 'OK':
                    for acc in self.page.iter_accounts():
                        acc.owner_type = AccountOwnerType.ORGANIZATION
                        if acc._parent_id:
                            acc.parent = find_object(accounts, _id=acc._parent_id)
                        yield acc

        # retrieve market accounts if exist
        for market_account in self.iter_market_accounts():
            acc.owner_type = AccountOwnerType.ORGANIZATION
            yield market_account

    @need_login
    def iter_history(self, account):
        if account.type in (
            account.TYPE_MARKET, account.TYPE_PER, account.TYPE_LIFE_INSURANCE, account.TYPE_CARD,
            account.TYPE_LOAN,
        ):
            # market account transactions are in checking account
            return

        value = self.history.go(data={'cl500_compte': account._id, 'cl200_typeReleve': 'valeur'}).get_value()

        self.history.go(data={'cl500_compte': account._id, 'cl200_typeReleve': value})
        for tr in self.page.iter_history(value=value):
            yield tr

        self.location('/icd/syd-front/data/syd-intraday-chargerDetail.json', data={'cl500_compte': account._id})
        for tr in self.page.iter_history():
            yield tr

    def encode_b64(self, string):
        return b64encode(string.encode('utf8')).decode('utf8')

    @need_login
    def get_cb_operations(self, account):
        if account.type != account.TYPE_CARD:
            return []

        self.cards_information.go()
        card_id = self.page.get_card_id()

        self.deferred_card.go(card_id=card_id)
        account_id = self.page.get_account_id()
        bank_code = self.page.get_bank_code()

        information_compte = {
            'codeBanque': self.encode_b64(bank_code),
            'codeGuichetCreateur': self.encode_b64(account_id[11:16]),
            'numCompte': self.encode_b64(account_id[16:27]),
            'intitule': self.encode_b64('Compte frais'),  # Seems to be useless
            'devise': self.encode_b64(account.currency),
            'dateImputation': None,
            'alias': None,
            'numReleveLCR': None,
            'dateReglement': None,
            'idClasseur': 'MQ==',  # Corresponds to 1
        }

        data = {
            'cl2000_informationCompte': json.dumps(information_compte),
        }

        self.cards_information2.go(data=data)
        # Cards without a number are not activated yet: (no history available)
        if not self.response.json()['donnees']:
            return []

        number = self.page.get_number(masked_number=account._masked_card_number)
        date_reglement = self.page.get_due_date()

        information_compte['alias'] = self.encode_b64(number)
        information_compte['numReleveLCR'] = self.encode_b64(number)
        information_compte['dateReglement'] = self.encode_b64(date_reglement)

        data = {
            'cl2000_informationCompte': json.dumps(information_compte),
        }

        self.deferred_card_history.go(data=data)

        return self.page.iter_comings(date=date_reglement)

    @need_login
    def iter_market_orders(self, account):
        # there are no examples of Pro/Ent space with market accounts yet
        return []

    @need_login
    def get_profile(self):
        self.profile.stay_or_go()
        # It seems we encounter the same error as on AccountsJsonPage about expired password here
        reason = self.page.get_error_msg()
        if reason:
            if reason in ('chgt_mdp_oblig', 'chgt_mdp_init'):
                raise BrowserPasswordExpired('Veuillez vous rendre sur le site de la banque pour renouveler votre mot de passe')
            raise AssertionError('Error %s is not handled yet' % reason)
        return self.page.get_profile()


class SGEnterpriseBrowser(SGPEBrowser):
    BASEURL = 'https://entreprises.sg.fr'
    MENUID = 'BANREL'
    CERTHASH = '2231d5ddb97d2950d5e6fc4d986c23be4cd231c31ad530942343a8fdcc44bb99'
    HAS_CREDENTIALS_ONLY = False  # systematic 2FA on Ent

    # * Ent specific URLs

    unavailable = URL(r'/page-indisponible', UnavailablePage)

    # Bill
    subscription = URL(r'/icd/syd-front/data/syd-rce-accederDepuisMenu.json', BankStatementPage)
    subscription_search = URL(r'/icd/syd-front/data/syd-rce-lancerRecherche.json', BankStatementPage)

    # * Ent adapted URLs
    main_page = URL(
        r'https://entreprises.sg.fr',
        r'/sec/vk/gen_',
        MainPEPage
    )

    def load_state(self, state):
        if not self.is_interactive:
            # user not present: start up at login to raise NeedInteractiveFor2FA since 2FA is systematic
            state.pop('url', None)
        super(SGEnterpriseBrowser, self).load_state(state)

    @need_login
    def iter_market_accounts(self):
        self.accounts_main_page.go()
        # retrieve market accounts if exist
        market_accounts_link = self.page.get_market_accounts_link()

        # there are no examples of entreprise space with market accounts yet
        assert not market_accounts_link, 'There are market accounts, retrieve them.'
        return []

    @need_login
    def iter_investment(self, account):
        # there are no examples of entreprise space with market accounts yet
        return []

    @need_login
    def iter_subscription(self):
        subscriber = self.get_profile().name

        self.subscription.go()
        self.page.check_error()
        # set the max/min date to use them in iter_documents
        self.date_min, self.date_max = self.page.get_min_max_date()
        return self.page.iter_subscription(subscriber=subscriber)

    @need_login
    def iter_documents(self, subscribtion):
        # This quality website can only fetch documents through a form, looking for dates
        # with a range of 3 months maximum
        search_date_max = self.date_max
        search_date_min = None
        is_end = False

        # to avoid infinite loop
        counter = 0

        while not is_end and counter < 50:
            # search for every 2 months
            search_date_min = search_date_max - relativedelta(months=2)

            if search_date_min < self.date_min:
                search_date_min = self.date_min
                is_end = True

            if search_date_max <= self.date_min:
                break

            data = {
                'dt10_dateDebut': search_date_min.strftime('%d/%m/%Y'),
                'dt10_dateFin': search_date_max.strftime('%d/%m/%Y'),
                'cl2000_comptes': '["%s"]' % subscribtion.id,
                'cl200_typeRecherche': 'ADVANCED',
            }
            self.subscription_search.go(data=data)

            for doc in self.page.iter_documents():
                yield doc

            search_date_max = search_date_min - relativedelta(days=1)
            counter += 1


class SGProfessionalBrowser(SGPEBrowser):
    BASEURL = 'https://professionnels.sg.fr'
    MENUID = 'SBOREL'
    CERTHASH = '9f5232c9b2283814976608bfd5bba9d8030247f44c8493d8d205e574ea75148e'

    # * Pro specific URLs

    # Transfer
    transfer_dates = URL(r'/ord-web/ord//get-dates-execution.json', TransferDatesPage)
    easy_transfer = URL(r'/ord-web/ord//ord-virement-simplifie-emetteur.html', EasyTransferPage)
    internal_recipients = URL(r'/ord-web/ord//ord-virement-simplifie-beneficiaire.html', EasyTransferPage)
    external_recipients = URL(r'/ord-web/ord//ord-liste-compte-beneficiaire-externes.json', RecipientsJsonPage)
    init_transfer_page = URL(r'/ord-web/ord//ord-enregistrer-ordre-simplifie.json', TransferPage)
    sign_transfer_page = URL(r'/ord-web/ord//ord-verifier-habilitation-signature-ordre.json', SignTransferPage)
    confirm_transfer = URL(
        r'/ord-web/ord//ord-valider-signature-ordre.json',
        ConfirmTransferPage,
    )

    recipients = URL(r'/ord-web/ord//ord-gestion-tiers-liste.json', RecipientsJsonPage)
    add_recipient = URL(
        r'/ord-web/ord//ord-fragment-form-tiers.html\?cl_action=ajout&cl_idTiers=',
        AddRecipientPage
    )
    add_recipient_step = URL(
        r'/ord-web/ord//ord-tiers-calcul-bic.json',
        r'/ord-web/ord//ord-preparer-signature-destinataire.json',
        AddRecipientStepPage
    )
    confirm_new_recipient = URL(r'/ord-web/ord//ord-creer-destinataire.json', ConfirmRecipientPage)

    # Bill
    bank_statement_menu = URL(r'/icd/syd-front/data/syd-rce-accederDepuisMenu.json', BankStatementPage)
    bank_statement_search = URL(r'/icd/syd-front/data/syd-rce-lancerRecherche.json', BankStatementPage)

    # Wealth
    market_accounts = URL(r'/brs/cct/comti10.html', MarketAccountsPage)
    market_accounts_details = URL(r'/brs/cct/comti20.html', MarketAccountsDetailsPage)
    wealth_accounts = URL(
        r'/icd/npe/data/paramcomptes/getPrestationsEpargneByProfilByPage-authsec.json',
        WealthAccountsPage  # Contains LifeInsurances and PER accounts
    )
    markets_page = URL(r'/icd/npe/data/comptes-titres/findComptesTitresClasseurs-authsec.json', MarketAccountPage)
    investments_page = URL(r'/icd/npe/data/comptes-titres/findLignesCompteTitre-authsec.json', MarketInvestmentPage)

    # Loans
    corp_list = URL(r'/icd/eko/data/eko-getListePms-authsec.json', CorpListPage)
    pro_loans = URL(
        r'/icd/eko/data/eko-getListeCredits-authsec.json\?cl200_marche=PRO&cl200_duree=(?P<duration>.+)&b64e200_idPppm=(?P<corp_id>.+)',
        ProLoansPage
    )
    pro_loan_details = URL(r'/icd/eko/data/eko-getCredit-CLASSIQUE-authsec.json', ProLoanDetailsPage)

    # Others
    useless_page = URL(r'/icd-web/syd-front/index-comptes.html', UselessPage)
    error_page = URL(
        r'https://static.sg.fr/pro/erreur.html',
        r'https://.*/pro/erreur.html',
        ErrorPage
    )

    # * Pro adapted URLs
    main_page = URL(
        r'https://professionnels.sg.fr',
        r'/sec/vk/gen_',
        MainPEPage
    )

    date_max = None
    date_min = None

    new_rcpt_token = None
    new_rcpt_validate_form = None

    __states__ = ('new_rcpt_token', 'new_rcpt_validate_form', 'polling_transaction',)

    @need_login
    def get_accounts_list(self):
        yield from super().get_accounts_list()

        # retrieve pro loans
        yield from self.iter_pro_loans()

    @need_login
    def iter_market_accounts(self):
        self.markets_page.go()
        yield from self.page.iter_market_accounts()

        self.wealth_accounts.go()
        yield from self.page.iter_accounts()

        self.market_accounts.go()
        yield from self.page.iter_accounts()

    @need_login
    def iter_pro_loans(self):
        self.corp_list.go()
        for corp_id in self.page.get_corps_list():
            for duration in ('CT', 'MLT'):  # court terme && moyen long terme
                self.pro_loans.go(
                    duration=duration,
                    corp_id=quote_plus(corp_id),
                )
                for loan in self.page.iter_loans():
                    self.pro_loan_details.go(
                        params={
                            'b64e200_agence_Gest': '',
                            'b64e200_compte': '',
                            'b64e200_companyId': '',
                            'b64e200_contractId': '',
                            'b64e200_idPrestation': loan._prestation,
                            'b64e200_idPppm': corp_id,
                        }
                    )
                    if self.page.get_loan_status() != 'OK':
                        error_message = self.page.get_error_message()
                        if 'Détail indisponible' in error_message:
                            continue
                        else:
                            raise AssertionError(
                                f'Unhandled error on pro_loan_details page: {error_message}'
                            )
                    self.page.fill_loan(loan)
                    yield loan

    @need_login
    def iter_investment(self, account):
        if account.type not in (account.TYPE_MARKET,):
            return []

        if not account._prestation_number:
            self.market_accounts_details.go()
            if account.number != self.page.get_account_number():
                raise AssertionError('Multiple accounts to choose from. Needs to be developped')
            return self.page.iter_investment()

        self.investments_page.go(data={'cl2000_numeroPrestation': account._prestation_number})
        return self.page.iter_investment()

    def copy_recipient_obj(self, recipient):
        rcpt = Recipient()
        rcpt.id = recipient.iban
        rcpt.iban = recipient.iban
        rcpt.label = recipient.label
        rcpt.category = 'Externe'
        rcpt.enabled_at = date.today()
        return rcpt

    @need_login
    def new_recipient(self, recipient, **params):
        if 'code' in params:
            self.validate_rcpt_with_sms(params['code'])
            return self.page.rcpt_after_sms(recipient)

        data = {
            'n_nbOccurences': 1000,
            'n_nbOccurences_affichees': 0,
            'n_rang': 0,
        }
        self.recipients.go(data=data)

        step_urls = {
            'first_recipient_check': self.absurl('/ord-web/ord//ord-valider-destinataire-avant-maj.json', base=True),
            'get_bic': self.absurl('/ord-web/ord//ord-tiers-calcul-bic.json', base=True),
            'get_token': self.absurl('/ord-web/ord//ord-preparer-signature-destinataire.json', base=True),
            'get_sign_info': self.absurl('/sec/getsigninfo.json', base=True),
            'send_otp_to_user': self.absurl('/sec/csa/send.json', base=True),
        }

        self.add_recipient.go(method='POST', headers={'Content-Type': 'application/json;charset=UTF-8'})
        countries = self.page.get_countries()

        # first recipient check
        data = {
            'an_codeAction': 'ajout_tiers',
            'an_refSICoordonnee': '',
            'an_refSITiers': '',
            'cl_iban': recipient.iban,
            'cl_raisonSociale': recipient.label,
        }
        self.location(step_urls['first_recipient_check'], data=data)

        # get bic
        data = {
            'an_activateCMU': 'true',
            'an_codePaysBanque': '',
            'an_nature': 'C',
            'an_numeroCompte': recipient.iban,
            'an_topIBAN': 'true',
            'cl_adresse': '',
            'cl_adresseBanque': '',
            'cl_codePays': recipient.iban[:2],
            'cl_libellePaysBanque': '',
            'cl_libellePaysDestinataire': countries[recipient.iban[:2]],
            'cl_nomBanque': '',
            'cl_nomRaisonSociale': recipient.label,
            'cl_ville': '',
            'cl_villeBanque': '',
        }
        self.location(step_urls['get_bic'], data=data)
        bic = self.page.get_response_data()

        # get token
        data = {
            'an_coordonnee_codePaysBanque': '',
            'an_coordonnee_nature': 'C',
            'an_coordonnee_numeroCompte': recipient.iban,
            'an_coordonnee_topConfidentiel': 'false',
            'an_coordonnee_topIBAN': 'true',
            'an_refSICoordonnee': '',
            'an_refSIDestinataire': '',
            'cl_adresse': '',
            'cl_codePays': recipient.iban[:2],
            'cl_coordonnee_adresseBanque': '',
            'cl_coordonnee_bic': bic,
            'cl_coordonnee_categories_libelle': '',
            'cl_coordonnee_categories_refSi': '',
            'cl_coordonnee_libellePaysBanque': '',
            'cl_coordonnee_nomBanque': '',
            'cl_coordonnee_villeBanque': '',
            'cl_libellePaysDestinataire': countries[recipient.iban[:2]],
            'cl_nomRaisonSociale': recipient.label,
            'cl_ville': '',
        }
        self.location(step_urls['get_token'], data=data)
        self.new_rcpt_validate_form = data
        payload = self.page.get_response_data()

        # get sign info
        data = {
            'b64_jeton_transaction': payload['jeton'],
            'action_level': payload['sensibilite'],
        }
        self.location(step_urls['get_sign_info'], data=data)

        # send otp to user
        data = {
            'context': payload['jeton'],
            'csa_op': 'sign',
        }
        self.location(step_urls['send_otp_to_user'], data=data)
        self.new_rcpt_validate_form.update(data)

        rcpt = self.copy_recipient_obj(recipient)
        raise AddRecipientStep(rcpt, Value('code', label='Veuillez entrer le code reçu par SMS.'))

    @retry(BrowserUnavailable)
    def go_confirm_new_recipient(self, data):
        page = self.confirm_new_recipient.go(data=data)
        page.check_error()

    @need_login
    def validate_rcpt_with_sms(self, code):
        assert self.new_rcpt_validate_form, 'There should have recipient validate form in states'
        self.new_rcpt_validate_form['code'] = code
        try:
            self.go_confirm_new_recipient(data=self.new_rcpt_validate_form)
        except ClientError as e:
            assert e.response.status_code == 403, (
                'Something went wrong in add recipient, response status code is %s' % e.response.status_code
            )
            raise AddRecipientBankError(message='Le code entré est incorrect.')

    @need_login
    def iter_recipients(self, origin_account, ignore_errors=True):
        self.easy_transfer.go()
        self.page.update_origin_account(origin_account)

        if not hasattr(origin_account, '_product_code'):
            # check that origin account is updated, if not, this account can't do transfer
            return

        params = {
            'cl_ibanEmetteur': origin_account.iban,
            'cl_codeProduit': origin_account._product_code,
            'cl_codeSousProduit': origin_account._underproduct_code,
        }
        self.internal_recipients.go(method='POST', params=params, headers={'Content-Type': 'application/json;charset=UTF-8'})
        for internal_rcpt in self.page.iter_internal_recipients():
            yield internal_rcpt

        data = {
            'an_filtreIban': 'true',
            'an_filtreIbanSEPA': 'true',
            'an_isCredit': 'true',
            'an_isDebit': 'false',
            'an_rang': 0,
            'an_restrictFRMC': 'false',
            'cl_codeProduit': origin_account._product_code,
            'cl_codeSousProduit': origin_account._underproduct_code,
            'n_nbOccurences': '10000',
        }
        self.external_recipients.go(data=data)
        self.page.check_error()

        if self.page.is_external_recipients():
            assert self.page.is_all_external_recipient(), "Some recipients are missing"
            for external_rcpt in self.page.iter_external_recipients():
                yield external_rcpt

    @need_login
    def init_transfer(self, account, recipient, transfer):
        self.transfer_dates.go()
        self.page.check_error()
        if not self.page.is_date_valid(transfer.exec_date):
            raise TransferBankError(message="La date d'exécution du virement est invalide. Elle doit correspondre aux horaires et aux dates d'ouvertures d'agence.")

        # update account and recipient info
        recipient = find_object(
            self.iter_recipients(account, ignore_errors=False),
            iban=recipient.iban, id=recipient.id, error=RecipientNotFound
        )

        data = [
            ('an_codeAction', 'C'),
            ('an_referenceSiOrdre', ''),
            ('cl_compteEmetteur_intitule', account._account_title),
            ('cl_compteEmetteur_libelle', account.label),
            ('an_compteEmetteur_iban', account.iban),
            ('cl_compteEmetteur_ibanFormate', account._formatted_iban),
            ('an_compteEmetteur_bic', account._bic),
            ('b64_compteEmetteur_idPrestation', account._id_service),
            ('an_guichetGestionnaire', account._manage_counter),
            ('an_codeProduit', account._product_code),
            ('an_codeSousProduit', account._underproduct_code),
            ('n_soldeComptableVeilleMontant', int(account.balance * (10 ** account._decimal_code))),
            ('n_soldeComptableVeilleCodeDecimalisation', account._decimal_code),
            ('an_soldeComptableVeilleDevise', account._currency_code),
            ('n_ordreMontantValeur', int(transfer.amount * (10 ** account._decimal_code))),
            ('n_ordreMontantCodeDecimalisation', account._decimal_code),
            ('an_ordreMontantCodeDevise', account._currency_code),
            ('cl_dateExecution', transfer.exec_date.strftime('%d/%m/%Y')),
            ('cl_ordreLibelle', transfer.label),
            ('an_beneficiaireCodeAction', 'C'),
            ('cl_beneficiaireRefSiCoordonnee', recipient._ref),
            ('cl_beneficiaireCompteLibelle', recipient.label),
            ('cl_beneficiaireCompteIntitule', recipient._account_title),
            ('cl_beneficiaireCompteIbanFormate', recipient._formatted_iban),
            ('an_beneficiaireCompteIban', recipient.iban),
            ('cl_beneficiaireCompteBic', recipient._bic),
            ('cl_beneficiaireDateCreation', recipient._created_date),
            ('cl_beneficiaireCodeOrigine', recipient._code_origin),
            ('cl_beneficiaireAdressePays', recipient.iban[:2]),
            ('an_indicateurIntraAbonnement', 'false'),
            ('cl_reference', ' '),
            ('cl_motif', transfer.label),
        ]
        # WARNING: this save transfer information on user account
        self.init_transfer_page.go(data=data)
        self.page.check_error()
        return self.page.handle_response(account, recipient, transfer.amount, transfer.label, transfer.exec_date)

    @need_login
    def execute_transfer(self, transfer, **params):
        assert transfer._b64_id_transfer, 'Transfer token is missing'
        # get virtual keyboard
        data = {
            'b64_idOrdre': transfer._b64_id_transfer,
        }
        self.sign_transfer_page.go(data=data)

        data.update(self.page.get_confirm_transfer_data(self.password))
        self.confirm_transfer.go(data=data)
        self.page.check_error()

        assert self.confirm_transfer.is_here(), (
            'An error occurred, we should be on confirm transfer page.'
        )

        self.page.raise_on_status()

        # Go on the accounts page to avoid reloading the confirm_transfer
        # url in locate_browser.
        self.accounts.go()
        self.page.check_error()
        return transfer

    @need_login
    def iter_subscription(self):
        profile = self.get_profile()
        subscriber = profile.name

        self.bank_statement_menu.go()
        self.page.check_error()
        self.date_min, self.date_max = self.page.get_min_max_date()
        return self.page.iter_subscription(subscriber=subscriber)

    @need_login
    def iter_documents(self, subscribtion):
        # This quality website can only fetch documents through a form, looking for dates
        # with a range of 3 months maximum
        search_date_max = self.date_max
        search_date_min = None
        is_end = False

        # to avoid infinite loop
        counter = 0

        while not is_end and counter < 50:
            # search for every 2 months
            search_date_min = search_date_max - relativedelta(months=2)

            if search_date_min < self.date_min:
                search_date_min = self.date_min
                is_end = True

            if search_date_max <= self.date_min:
                break

            data = {
                'dt10_dateDebut': search_date_min.strftime('%d/%m/%Y'),
                'dt10_dateFin': search_date_max.strftime('%d/%m/%Y'),
                'cl2000_comptes': '["%s"]' % subscribtion.id,
                'cl200_typeRecherche': 'ADVANCED',
            }
            self.bank_statement_search.go(data=data)

            for d in self.page.iter_documents():
                yield d

            search_date_max = search_date_min - relativedelta(days=1)
            counter += 1

    @need_login
    def iter_emitters(self):
        self.easy_transfer.go()
        return self.page.iter_emitters()
