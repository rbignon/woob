# Copyright(C) 2016     Baptiste Delpey
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
from datetime import datetime
from decimal import Decimal
from urllib.parse import quote_plus

import requests

from woob.browser.pages import JsonPage, pagination
from woob.browser.elements import ItemElement, method, DictElement
from woob.browser.filters.standard import (
    CleanDecimal, CleanText, Coalesce, Date, Eval, Format, BrowserURL, Env,
    Field, MapIn, Regexp, Currency as CurrencyFilter,
)
from woob.browser.filters.json import Dict
from woob.capabilities.bank.base import Loan
from woob.capabilities.base import Currency, empty
from woob.capabilities import NotAvailable
from woob.capabilities.bank import Account, NoAccountsException
from woob.capabilities.bank.wealth import Investment
from woob.capabilities.bill import Document, Subscription, DocumentTypes
from woob.capabilities.profile import Person
from woob.exceptions import (
    ActionNeeded, ActionType, AuthMethodNotImplemented, BrowserPasswordExpired,
    BrowserUnavailable,
)
from woob.capabilities.bank import AccountOwnerType
from woob.tools.capabilities.bank.iban import is_iban_valid
from woob.tools.capabilities.bank.transactions import FrenchTransaction
from woob.tools.capabilities.bank.investments import is_isin_valid

from .pages import Transaction


class LoggedDetectionMixin(object):
    @property
    def logged(self):
        return Dict('commun/raison', default=None)(self.doc) != "niv_auth_insuff"


class SGPEJsonPage(LoggedDetectionMixin, JsonPage):
    pass


ACCOUNT_TYPES = {
    'COMPTE COURANT': Account.TYPE_CHECKING,
    'COMPTE PERSONNEL': Account.TYPE_CHECKING,
    'CPTE PRO': Account.TYPE_CHECKING,
    'CPTE PERSO': Account.TYPE_CHECKING,
    'CODEVI': Account.TYPE_SAVINGS,
    'CEL': Account.TYPE_SAVINGS,
    'Ldd': Account.TYPE_SAVINGS,
    'Livret': Account.TYPE_SAVINGS,
    'PEL': Account.TYPE_SAVINGS,
    'CPTE TRAVAUX': Account.TYPE_SAVINGS,
    'EPARGNE': Account.TYPE_SAVINGS,
    'Plan Epargne': Account.TYPE_SAVINGS,
    'PEA': Account.TYPE_PEA,
    'Prêt': Account.TYPE_LOAN,
    'VIE': Account.TYPE_LIFE_INSURANCE,
}


class AccountsJsonPage(SGPEJsonPage):
    ENCODING = 'utf-8'

    def check_error(self):
        if self.doc['commun']['statut'].lower() == 'nok':
            reason = self.doc['commun']['raison']
            if reason == 'SYD-COMPTES-UNAUTHORIZED-ACCESS':
                raise NoAccountsException("Vous n'avez pas l'autorisation de consulter : {}".format(reason))
            elif reason == 'niv_auth_insuff':
                raise AssertionError(reason)
            elif reason in ('chgt_mdp_oblig', 'chgt_mdp_init'):
                raise BrowserPasswordExpired('Veuillez vous rendre sur le site de la banque pour renouveler votre mot de passe')
            elif reason == 'oob_insc_oblig':
                raise AuthMethodNotImplemented("L'authentification par Secure Access n'est pas prise en charge")
            elif reason in ('err_is', 'err_tech'):
                raise BrowserUnavailable()
            elif reason in ('ENCADREMENT_KYC_PREAVIS', 'ENCADREMENT_KYC_POST_PREAVIS'):
                raise ActionNeeded(
                    locale="fr-FR", message="Votre banque requiert des informations complémentaires pour mettre à jour votre dossier client.",
                    action_type=ActionType.FILL_KYC,
                )
            elif reason in ('INSCRIP_OBL', 'FIABILISATION_COORDONNEES'):
                raise ActionNeeded(
                    locale="fr-FR", message="Veuillez vous rendre sur le site de votre banque pour completer vos informations.",
                    action_type=ActionType.FILL_KYC,
                )
            else:
                # the BrowserUnavailable was raised for every unknown error, and was masking the real error.
                # So users and developers didn't know what kind of error it was.
                raise AssertionError('Error %s is not handled yet' % reason)

    @method
    class iter_class_accounts(DictElement):
        item_xpath = 'donnees/classeurs'

        class iter_accounts(DictElement):
            def find_elements(self):
                element = self.el.get('intradayComptes') or self.el.get('comptes')
                if element:
                    return element
                return []

            class item(ItemElement):
                klass = Account

                obj__id = Dict('id')
                obj_number = CleanText(Dict('iban'), replace=[(' ', '')])  # yes, IBAN is presented as number to user
                obj_iban = Field('number')
                obj_label = CleanText(Dict('libelle'))
                obj__agency = Dict('agenceGestionnaire')

                def obj_id(self):
                    number = Field('number')(self)
                    if len(number) == 27:
                        # id based on iban to match ids in database.
                        return number[4:-2]
                    return number

                def obj_iban(self):
                    # for some account that don't have Iban the account number is store under this variable in the Json
                    number = Field('number')(self)
                    if not is_iban_valid(number):
                        return NotAvailable
                    return number

                def obj_type(self):
                    return self.page.acc_type(Field('label')(self))

    def acc_type(self, label):
        for wording, acc_type in ACCOUNT_TYPES.items():
            if wording.lower() in label.lower():
                return acc_type
        return Account.TYPE_CHECKING

    def get_error(self):
        if self.doc['commun']['statut'] == 'nok':
            # warning: 'nok' is case sensitive, for wrongpass at least it's 'nok'
            # for certain other errors (like no accounts), it's 'NOK'
            return self.doc['commun']['raison']
        return None


class CardsInformationPage(SGPEJsonPage):
    def get_card_id(self):
        return self.response.json()['donnees'][0].get('idPPouPM')


class CardsInformation2Page(SGPEJsonPage):
    def get_number(self, masked_number):
        def match(card, masked_number):
            """
            masked number : 949021XXXXXX9429000
            striped masked number : 949021XXXXXX9429
            masked number regex : 949021.*9429
            number: 000009490219329019429
            striped_number: 9490219329019429
            """
            number = card['numero']
            striped_number = number.lstrip('0')
            striped_masked_number = masked_number.rstrip('0')
            masked_number_regex = re.sub(r'X+', '.*', striped_masked_number)
            return re.match(masked_number_regex, striped_number)

        cards = self.response.json().get('donnees')
        for card in cards:
            if match(card, masked_number):
                return card['numero']
        return ''

    def get_due_date(self):
        """
        Sometimes we get several cards even though we asked for one,
        and they have the same number but some may not have a date.
        """
        data = self.doc['donnees']

        for element in data:
            freeze_date = element.get('dateRegelement')
            if freeze_date and freeze_date != "Non définie":
                return freeze_date


class DeferredCardJsonPage(SGPEJsonPage):
    def get_account_id(self):
        return self.response.json().get('donnees')[0].get('idPrestationCompte')

    def get_bank_code(self):
        return self.response.json().get('donnees')[0].get('entiteJuridiquePDG')

    @method
    class iter_accounts(DictElement):
        item_xpath = 'donnees'

        class item(ItemElement):
            klass = Account

            def condition(self):
                return (
                    not Dict('inactivityDate', default='')(self)  # Is not always present in json
                    and Dict('currentOutstandingAmountDate')(self)  # avoid immediate debit cards
                )

            obj_id = Coalesce(
                Dict('numeroCarte', default=NotAvailable),
                Dict('numeroCarteHash', default=NotAvailable)
            )
            obj_number = Coalesce(
                Dict('numeroCarte', default=NotAvailable),
                Dict('maskedCardNumber', default=NotAvailable),
                default=NotAvailable
            )
            obj_label = CleanText(Dict('libelle'))
            obj_type = Account.TYPE_CARD
            obj_coming = CleanDecimal.French(Dict('encoursToShow'))
            obj_currency = CurrencyFilter(Dict('currentOutstandingAmount/devise'))
            obj__parent_id = Dict('idPrestationCompte', default=NotAvailable)
            obj__masked_card_number = Dict('maskedCardNumber', default=NotAvailable)


class DeferredCardHistoryJsonPage(SGPEJsonPage):
    @method
    class iter_comings(DictElement):
        item_xpath = 'donnees'

        class item(ItemElement):
            klass = Transaction

            obj_date = Date(Env('date'), dayfirst=True)
            obj_rdate = Date(CleanText(Dict('date')), dayfirst=True, default=NotAvailable)
            obj_label = CleanText(Dict('libelle'))
            obj_type = Transaction.TYPE_DEFERRED_CARD  # card summaries only on parent account side

            def obj_amount(self):
                return Decimal(Dict('montant/montant')(self)) / (10 ** Decimal(Dict('montant/nbrDecimales')(self)))


class BalancesJsonPage(SGPEJsonPage):
    def on_load(self):
        if self.doc['commun']['statut'] == 'NOK':
            reason = self.doc['commun']['raison']
            if reason == 'SYD-COMPTES-UNAUTHORIZED-ACCESS':
                raise NoAccountsException("Vous n'avez pas l'autorisation de consulter : {}".format(reason))
            raise BrowserUnavailable(reason)

    def populate_balances(self, accounts):
        for account in accounts:
            acc_dict = self.doc['donnees']['compteSoldesMap'][account._id]
            account.balance = CleanDecimal(replace_dots=True).filter(acc_dict.get('soldeComptable', acc_dict.get('soldeInstantane')))
            account.currency = Currency.get_currency(acc_dict.get('deviseSoldeComptable', acc_dict.get('deviseSoldeInstantane')))
            account.coming = CleanDecimal(replace_dots=True, default=NotAvailable).filter(acc_dict.get('montantOperationJour'))
            yield account


class HistoryJsonPage(SGPEJsonPage):

    def get_value(self):
        if 'NOK' in self.doc['commun']['statut']:
            return 'position'
        else:
            return 'valeur'

    @pagination
    @method
    class iter_history(DictElement):
        def __init__(self, *args, **kwargs):
            super(DictElement, self).__init__(*args, **kwargs)

        @property
        def item_xpath(self):
            if 'Prochain' not in self.page.url:
                return 'donnees/compte/operations'
            return 'donnees/ecritures'

        def condition(self):
            return 'donnees' in self.page.doc

        def next_page(self):
            if 'Prochain' not in self.page.url:
                d = self.page.doc['donnees']['compte']
            else:
                d = self.page.doc['donnees']

            if 'ecrituresRestantes' in d:
                next_ope = d['ecrituresRestantes']
                next_data = d['sceauEcriture']
            else:
                next_ope = d['operationsRestantes']
                next_data = d['sceauOperation']

            if next_ope:
                data = {}
                data['b64e4000_sceauEcriture'] = next_data
                if 'intraday' not in self.page.url:
                    data['cl200_typeReleve'] = Env('value')(self)
                return requests.Request("POST", BrowserURL('history_next')(self), data=data)

        class item(ItemElement):
            klass = Transaction

            obj_rdate = Env('rdate')
            obj_date = Env('date')
            obj__coming = False

            # Label is split into l1, l2, l3, l4, l5.
            # l5 is needed for transfer label, for example:
            # 'l1': "000001 VIR EUROPEEN EMIS   NET"
            # 'l2': "POUR: XXXXXXXXXXXXX"
            # 'l3': "REF: XXXXXXXXXXXXXX"
            # 'l4': "REMISE: XXXXXX TRANSFER LABEL"
            # 'l5': "MOTIF: TRANSFER LABEL"
            obj_raw = Transaction.Raw(Format(
                '%s %s %s %s %s',
                Dict('l1'),
                Dict('l2'),
                Dict('l3'),
                Dict('l4'),
                Dict('l5'),
            ))

            # keep the 3 first rows for transaction label
            obj_label = Transaction.Raw(Format(
                '%s %s %s',
                Dict('l1'),
                Dict('l2'),
                Dict('l3'),
            ))

            def obj_commission(self):
                if Regexp(
                        Field('label'),
                        r' ([\d{1,3}\s?]*\d{1,3},\d{2}E COM [\d{1,3}\s?]*\d{1,3},\d{2}E)',
                        default=''
                )(self):
                    # commission can be scraped from labels like 'REMISE CB /14/08 XXXXXX YYYYYYYYYYY ZZ 105,00E COM 0,84E'
                    return CleanDecimal.French(
                        Regexp(Field('label'), r'COM ([\d{1,3}\s?]*\d{1,3},\d{2})E', default=''),
                        sign='-',
                        default=NotAvailable
                    )(self)

                return NotAvailable

            def obj_gross_amount(self):
                if not empty(Field('commission')(self)):
                    # gross_amount can be scraped from labels like 'REMISE CB /14/08 XXXXXX YYYYYYYYYYY ZZ 105,00E COM 0,84E'
                    return CleanDecimal.French(
                        Regexp(Field('label'), r' ([\d{1,3}\s?]*\d{1,3},\d{2})E COM', default=''),
                        default=NotAvailable
                    )(self)

                return NotAvailable

            def obj_amount(self):
                return (
                    CleanDecimal(Dict('c', default=None), replace_dots=True, default=None)(self)
                    or CleanDecimal(Dict('d'), replace_dots=True)(self)
                )

            def obj_deleted(self):
                return self.obj.type == FrenchTransaction.TYPE_CARD_SUMMARY

            def parse(self, el):
                self.env['rdate'] = Date(Dict('date', default=None), dayfirst=True, default=NotAvailable)(self)
                self.env['date'] = Date(Dict('dVl', default=None), dayfirst=True, default=NotAvailable)(self)

                if 'REGULARISATION DE COMMISSION' in Dict('l1')(self) and self.env['date'] < self.env['rdate']:
                    # transaction corresponding a bank reimbursement were date and rdate are inverted
                    # ex: 24/07 in Dict('dVl'), but 24/09 is in Dict('date');
                    # so for this particular transaction the order should be 24/07 (rdate)
                    # while the effective date of credit on the account should be 27/09 (date)
                    self.env['rdate'], self.env['date'] = self.env['date'], self.env['rdate']


class ProfilePEPage(SGPEJsonPage):
    def get_error_msg(self):
        if self.doc['commun']['statut'].lower() == 'nok':
            return self.doc['commun']['raison']

    @method
    class get_profile(ItemElement):
        klass = Person

        obj_name = Format(
            '%s %s %s',
            Dict('donnees/civiliteLong'),
            Dict('donnees/prenom'),
            Dict('donnees/nom'),
        )

        obj_phone = Coalesce(
            Dict('donnees/telephoneSecurite', default=NotAvailable),
            Dict('donnees/telephoneMobile', default=NotAvailable),
            Dict('donnees/telephoneFixe', default=NotAvailable),
            default=NotAvailable,
        )

        obj_email = Coalesce(
            Dict('donnees/email', default=NotAvailable),
            Dict('donnees/emailAlertes', default=NotAvailable),
            default=NotAvailable,
        )

        obj_job = Dict('donnees/fonction/libelle', default=NotAvailable)
        obj_company_name = Dict('donnees/raisonSocialeEntreprise', default=NotAvailable)


class BankStatementPage(SGPEJsonPage):
    def is_document_disabled(self):
        # If e-document is not activated by the account owner, we have this specific response.
        # So, if Bank statements are not available we don't want to break the run.
        if self.doc.get('commun', {}).get('statut').lower() == 'nok':
            reason = self.doc.get('commun', {}).get('raison')
            if reason == 'SYD-RCE-UNAUTHORIZED-ACCESS':
                self.logger.warning('No subscriptions access rights granted: %s', reason)
                return True
        return False

    def check_error(self):
        if self.doc.get('commun', {}).get('statut').lower() == 'nok':
            reason = self.doc.get('commun', {}).get('raison')
            if reason == 'oob_insc_oblig':
                raise AuthMethodNotImplemented("L'authentification par Secure Access n'est pas prise en charge")
            raise AssertionError(f'Error {reason} is not handled yet')

    def get_min_max_date(self):
        min_date = Date(Dict('donnees/criteres/dateMin'), dayfirst=True, default=None)(self.doc)
        max_date = Date(Dict('donnees/criteres/dateMax'), dayfirst=True, default=None)(self.doc)
        assert min_date and max_date, 'There should have min date and max date to retrieve document'
        return min_date, max_date

    @method
    class iter_subscription(DictElement):
        item_xpath = 'donnees/comptes'

        class item(ItemElement):
            klass = Subscription

            obj_id = Dict('id')
            obj_label = Dict('libelle')
            obj_subscriber = Env('subscriber')

    def iter_documents(self):
        account, = self.doc['donnees']['comptes']
        statements = account['releves']

        for document in statements:
            d = Document()
            d.date = datetime.strptime(document['dateEdition'], '%d/%m/%Y')
            d.label = '%s %s' % (account['libelle'], document['dateEdition'])
            d.type = DocumentTypes.STATEMENT
            d.format = 'pdf'
            d.id = '%s_%s' % (account['id'], document['dateEdition'].replace('/', ''))
            d.url = '/icd/syd-front/data/syd-rce-telechargerReleve.html?b64e4000_sceau=%s' % quote_plus(document['sceau'])

            yield d


class MarketAccountPage(SGPEJsonPage):
    @method
    class iter_market_accounts(DictElement):
        item_xpath = 'donnees/comptesTitresByClasseur'

        def condition(self):
            # Some 'comptesTitresByClasseur' do not have a 'list' key
            # and therefore have no account list, we skip them
            return Dict('list', default=None)(self)

        class iter_accounts(DictElement):
            item_xpath = 'list'

            class item(ItemElement):
                klass = Account

                obj__prestation_number = Dict('numeroPrestation')

                obj_id = Format('%s_TITRE', CleanText(Field('_prestation_number'), replace=[(' ', '')]))
                obj_number = CleanText(Field('_prestation_number'), replace=[(' ', '')])
                obj_label = Dict('intitule')
                obj_balance = CleanDecimal.French(Dict('evaluation'))
                obj_currency = CurrencyFilter(Dict('evaluation'))
                obj_type = Account.TYPE_MARKET


class MarketInvestmentPage(SGPEJsonPage):
    @method
    class iter_investment(DictElement):
        item_xpath = 'donnees'

        class item(ItemElement):
            klass = Investment

            obj_label = Dict('libelle')
            obj_valuation = CleanDecimal.French(Dict('valorisation'))
            obj_quantity = CleanDecimal.French(Dict('quantite'))
            obj_unitvalue = CleanDecimal.French(Dict('cours'))

            def obj_code(self):
                code = Dict('codeISIN')(self)
                if is_isin_valid(code):
                    return code
                return NotAvailable

            def obj_code_type(self):
                if empty(Field('code')(self)):
                    return NotAvailable
                return Investment.CODE_TYPE_ISIN


class WealthAccountsPage(SGPEJsonPage):
    @method
    class iter_accounts(DictElement):
        item_xpath = 'donnees'

        class item(ItemElement):
            klass = Account

            def condition(self):
                # At least some PER have no balance and no information at all except
                # a label and a contract number. Clicking on those PER on the website
                # leads to an error page so we skip them for the moment
                return Dict('soldeAfficher')(self)

            obj_number = obj_id = CleanText(Dict('numeroContrat'))
            obj_label = CleanText(Dict('intitule'))
            obj_balance = CleanDecimal.French(Dict('soldeAfficher'))
            obj_currency = CurrencyFilter(Dict('devise'))
            obj_type = MapIn(Dict('typeProduit'), ACCOUNT_TYPES, Account.TYPE_UNKNOWN)
            obj__prestation_number = None


class CorpListPage(SGPEJsonPage):
    def get_corps_list(self):
        for corp in Dict('donnees/listFilterPms')(self.doc):
            yield corp['id']


class ProLoansPage(SGPEJsonPage):
    @method
    class iter_loans(DictElement):
        item_xpath = 'donnees/listeCredits/*'

        class item(ItemElement):
            klass = Loan

            def condition(self):
                # This is needed to avoid fetching some short-term credits that are not regular
                # credits (only information for them are an iban and some sort of maximum amount).
                # We also skip some almost empty mid-term credits called "Crédit-Bail-Mobilier"
                # or "Location avec Option d'Achat"
                if Dict('typeCredit')(self) not in ('CLASSIQUE', 'LOA', 'CBM'):
                    self.logger.warning('Unknown type of loan: %s', Dict('typeCredit')(self))
                return (
                    Dict('libelleLong')(self) != 'Autorisation de découvert (Convention de Trésorerie Courante)'
                    and Dict('typeCredit')(self) == 'CLASSIQUE'
                )

            obj_number = obj_id = CleanText(Dict('numContract'))
            obj_label = Format(
                '%s n°%s%s',
                CleanText(Dict('libelleCourt')),
                Field('number'),
                CleanText(Dict('informationFacultative'), default=''),  # Value looks like " : Matériel"
            )
            obj_type = Account.TYPE_LOAN
            obj_owner_type = AccountOwnerType.ORGANIZATION
            obj__prestation = CleanText(Dict('idPrestation'))


class ProLoanDetailsPage(SGPEJsonPage):
    def get_loan_status(self):
        return Dict('commun/statut')(self.doc)

    def get_error_message(self):
        return Dict('commun/raison')(self.doc)

    @method
    class fill_loan(ItemElement):
        klass = Loan

        item_xpath = 'donnees'

        obj_balance = CleanDecimal.French(Dict('montantRestantDu'), sign='-')
        obj_currency = CurrencyFilter(Dict('montantRestantDu'))
        obj_total_amount = CleanDecimal.French(Dict('capitalEmprunte'))
        obj_duration = Eval(int, CleanDecimal(Dict('dureeCredit')))
        obj_subscription_date = Date(CleanText(Dict('dateDebutCreditTime')))
        obj_maturity_date = Date(CleanText(Dict('dateFinCreditTime')))
        obj_last_payment_amount = CleanDecimal.French(Dict('montantDerniereEcheance'), default=NotAvailable)
        obj_last_payment_date = Date(CleanText(Dict('dateDerniereEcheanceTime'), default=''), default=NotAvailable)
        obj_next_payment_amount = CleanDecimal.French(Dict('montantProchaineEcheance'), default=NotAvailable)
        obj_next_payment_date = Date(CleanText(Dict('dateProchaineEcheanceTime'), default=''), default=NotAvailable)
