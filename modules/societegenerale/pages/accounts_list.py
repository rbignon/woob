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

from __future__ import annotations

import datetime
import re
from itertools import zip_longest
from urllib.parse import urlencode, urlsplit, urlunsplit

import requests
from schwifty import BIC, IBAN

from woob.browser.elements import DictElement, ItemElement, ListElement, TableElement, method
from woob.browser.filters.html import Attr, Link, TableCell
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import (
    Base, CleanDecimal, CleanText, Coalesce, Currency, Date, Env, Eval, Field, Format, Lower, Map, MapIn, Regexp,
)
from woob.browser.pages import HTMLPage, JsonPage, LoggedPage, XMLPage, pagination
from woob.capabilities.bank import Account, AccountOwnership, Loan, NoAccountsException, Recipient
from woob.capabilities.bank.wealth import (
    Investment, MarketOrder, MarketOrderDirection, MarketOrderPayment, MarketOrderType,
)
from woob.capabilities.base import NotAvailable, empty
from woob.capabilities.bill import Subscription
from woob.capabilities.contact import Advisor
from woob.capabilities.profile import Person, ProfileMissing
from woob.exceptions import BrowserUnavailable, BrowserUserBanned
from woob.tools.capabilities.bank.investments import IsinCode, IsinType, create_french_liquidity
from woob.tools.capabilities.bank.transactions import FrenchTransaction


class TemporaryBrowserUnavailable(BrowserUnavailable):
    # To handle temporary errors (like 'err_tech') that are usually
    # solved by just making a retry
    pass


def MyDecimal(*args, **kwargs):
    kwargs.update(replace_dots=True, default=NotAvailable)
    return CleanDecimal(*args, **kwargs)


def eval_decimal_amount(value, decimal_position):
    return Eval(lambda x,y: x / 10**y,
                CleanDecimal(Dict(value)),
                CleanDecimal(Dict(decimal_position)))


class JsonBasePage(LoggedPage, JsonPage):
    @property
    def logged(self):
        return Dict('commun/raison', default=None)(self.doc) != "niv_auth_insuff"

    def on_load(self):
        if Dict('commun/statut')(self.doc).upper() == 'NOK':
            reason = Dict('commun/raison')(self.doc)
            action = Dict('commun/action')(self.doc)

            if action and 'BLOCAGE' in action:
                raise BrowserUserBanned()

            if reason and 'err_tech' in reason:
                # This error is temporary and usually do not happens on the next try
                raise TemporaryBrowserUnavailable()

            if ('le service est momentanement indisponible' in reason and
            Dict('commun/origine')(self.doc) != 'cbo'):
                raise BrowserUnavailable()

            if reason == "niv_auth_insuff":
                return

            conditions = (
                'pas encore géré' in reason, # this page is not handled by SG api website
                'le service est momentanement indisponible' in reason,  # can't access new website
            )
            assert any(conditions), 'Error %s is not handled yet' % reason
            self.logger.warning('Handled Error "%s"', reason)


class HTMLLoggedPage(LoggedPage, HTMLPage):
    @property
    def logged(self):
        return self.doc.xpath('//a[@data-cms-callback-url="/page-deconnexion"]')


class AccountsMainPage(HTMLLoggedPage):
    def is_old_website(self):
        return Link('//a[contains(text(), "Afficher la nouvelle consultation")]', default=None)(self.doc)

    def is_accounts(self):
        error_msg = CleanText('//span[@class="error_msg"]')(self.doc)
        if 'Vous ne disposez pas de compte consultable' in error_msg:
            raise NoAccountsException(error_msg)

    @method
    class iter_accounts(TableElement):
        """iter account on old website"""
        head_xpath = '//table[@class="LGNTableA ListePrestation"]//tr[@class="LGNTableHead"]/th'
        item_xpath = '//table[@class="LGNTableA ListePrestation"]//tr[has-class("LGNTableRow")]'

        col_id = 'Numéro de Compte'
        col_type = 'Type de Compte'
        col_label = 'Libellé'
        col_balance = 'Solde'

        class item(ItemElement):
            klass = Account

            TYPES = {
                'LIVRET': Account.TYPE_SAVINGS,
            }

            obj_id = obj_number = CleanText(TableCell('id'), replace=[(' ', '')])
            obj_label = CleanText('.//span[@class="TypeCompte"]')
            obj_balance = MyDecimal(TableCell('balance'))
            obj_currency = Currency(CleanText(TableCell('balance')))
            obj__internal_id = None

            def obj_type(self):
                for acc_type in self.TYPES:
                    if acc_type in Field('label')(self).upper():
                        return self.TYPES[acc_type]
                return Account.TYPE_UNKNOWN


class AccountDetailsPage(LoggedPage, HTMLPage):
    pass


class AccountsPage(JsonBasePage):
    def is_new_website_available(self):
        if not Dict('commun/raison')(self.doc):
            return True
        elif 'le service est momentanement indisponible' not in Dict('commun/raison')(self.doc):
            return True
        self.logger.warning("SG new website is not available yet for this user")
        return False

    @method
    class iter_accounts(DictElement):
        item_xpath = 'donnees/syntheseParGroupeProduit/*/prestations'

        class item(ItemElement):
            def condition(self):
                return Dict('etatPrestation')(self) != 'INDISPONIBLE'

            klass = Account

            # There are more account type to find
            TYPES = {
                'COMPTE_COURANT': Account.TYPE_CHECKING,
                'PEL': Account.TYPE_SAVINGS,
                'CEL': Account.TYPE_SAVINGS,
                'LDD': Account.TYPE_SAVINGS,
                'LIVRETA': Account.TYPE_SAVINGS,
                'SOGEMONDE': Account.TYPE_SAVINGS,
                'LIVRET_JEUNE': Account.TYPE_SAVINGS,
                'LIVRET_EUROKID': Account.TYPE_SAVINGS,
                'COMPTE_SUR_LIVRET': Account.TYPE_SAVINGS,
                'LIVRET_EPARGNE_PLUS': Account.TYPE_SAVINGS,
                'PLAN_EPARGNE_BANCAIRE': Account.TYPE_SAVINGS,
                'PLAN_EPARGNE_POPULAIRE': Account.TYPE_SAVINGS,
                'LIVRET_EPARGNE_POPULAIRE': Account.TYPE_SAVINGS,
                'BANQUE_FRANCAISE_MUTUALISEE': Account.TYPE_SAVINGS,
                'PRET_GENERAL': Account.TYPE_LOAN,
                'PRET_PERSONNEL_MUTUALISE': Account.TYPE_LOAN,
                'DECLIC_TEMPO': Account.TYPE_MARKET,
                'COMPTE_TITRE_GENERAL': Account.TYPE_MARKET,
                'PEA_ESPECES': Account.TYPE_PEA,
                'PEA_PME_ESPECES': Account.TYPE_PEA,
                'COMPTE_TITRE_PEA': Account.TYPE_PEA,
                'COMPTE_TITRE_PEA_PME': Account.TYPE_PEA,
                'VIE_LMP': Account.TYPE_LIFE_INSURANCE,
                'PROJECTIS': Account.TYPE_LIFE_INSURANCE,
                'VIE_FEDER': Account.TYPE_LIFE_INSURANCE,
                'PALISSANDRE': Account.TYPE_LIFE_INSURANCE,
                'PROJECTIS_PROFESS': Account.TYPE_LIFE_INSURANCE,
                'SOGECAPI_PATRIMOINE': Account.TYPE_LIFE_INSURANCE,
                'EBENE_CAPITALISATION': Account.TYPE_LIFE_INSURANCE,
                'ASSURANCE_VIE_GENERALE': Account.TYPE_LIFE_INSURANCE,
                'ASSURANCE_VIE_SOGECAP_GENERAL': Account.TYPE_LIFE_INSURANCE,
                'VIE_AXA': Account.TYPE_LIFE_INSURANCE,
                'CAPI_AGF': Account.TYPE_LIFE_INSURANCE,
                'RESERVEA': Account.TYPE_REVOLVING_CREDIT,
                'COMPTE_ALTERNA': Account.TYPE_REVOLVING_CREDIT,
                'CREDIT_CONFIANCE': Account.TYPE_REVOLVING_CREDIT,
                'AVANCE_PATRIMOINE': Account.TYPE_REVOLVING_CREDIT,
                'PRET_EXPRESSO': Account.TYPE_CONSUMER_CREDIT,
                'PRET_EVOLUTIF': Account.TYPE_CONSUMER_CREDIT,
                'PERP_EPICEA': Account.TYPE_PERP,
                'PERIN_ACACIA_C1': Account.TYPE_PER,
            }

            ACCOUNTS_OWNERSHIP = {
                'COTITULAIRE': AccountOwnership.CO_OWNER,
                'MANDATAIRE': AccountOwnership.ATTORNEY,
                'REPRESENTATION': AccountOwnership.ATTORNEY,  # Credentials owner children
                'TITULAIRE': AccountOwnership.OWNER,
            }

            obj_id = obj_number = CleanText(Dict('numeroCompteFormate'), replace=[(' ', '')])
            obj_label = Dict('labelToDisplay')
            obj_iban = Dict('iban')
            obj_balance = CleanDecimal(Dict('soldes/soldeActuel'))
            obj_coming = CleanDecimal(Dict('soldes/soldeEnCours'))
            obj_currency = Currency(Dict('soldes/devise'))
            obj__cards = Dict('cartes', default=[])

            # Crédit de trésorerie can have codeFamille==PR_IMMO but their details are available
            # using the param a100_isPretConso=True.
            obj__is_tresorerie = Eval(lambda x: x == 'Crédit de trésorerie', Dict('libelleOriginal'))

            def obj_type(self):
                _type = self.TYPES.get(Dict('produit')(self), Account.TYPE_UNKNOWN)
                if not _type:
                    self.logger.warning('Account %s untyped, please type it.', Field('label')(self))
                elif Dict('codeFamille')(self) == 'PR_IMMO':
                    # Mortgage are typed like a standard loan
                    # Must use "codeFamille" to correctly type it.
                    return Account.TYPE_MORTGAGE
                return _type

            def obj_ownership(self):
                # 'groupeRoleDTO' can contains 'TITULAIRE', 'MANDATAIRE' or 'REPRESENTATION'
                # 'role' contains 'groupeRoleDTO' sub-categories. If the groupeRoleDTO is
                # 'TUTULAIRE', we have to check the role to know if it's 'TITULAIRE' or 'COTITULAIRE'
                ownership = Map(Dict('groupeRoleDTO'), self.ACCOUNTS_OWNERSHIP, NotAvailable)(self)
                if ownership == AccountOwnership.OWNER:
                    ownership = Map(Dict('role'), self.ACCOUNTS_OWNERSHIP, NotAvailable)(self)
                return ownership

            # Useful for navigation
            obj__internal_id = Dict('idTechnique')
            obj__prestation_id = Dict('id')

            def obj__loan_type(self):
                if Field('type')(self) in (
                    Account.TYPE_LOAN,
                    Account.TYPE_CONSUMER_CREDIT,
                    Account.TYPE_REVOLVING_CREDIT,
                    Account.TYPE_MORTGAGE,
                ):
                    return Dict('codeFamille')(self)
                return None

            def obj__is_json_histo(self):
                # For TYPE_REVOLVING_CREDIT, to get transaction
                if Field('type')(self) == Account.TYPE_REVOLVING_CREDIT and \
                not Dict('produit')(self) in ('COMPTE_ALTERNA', 'AVANCE_PATRIMOINE'):
                    return True
                # PLAN_EPARGNE_POPULAIRE account type history is not in json yet
                if Field('type')(self) == Account.TYPE_SAVINGS and \
                not Dict('produit')(self) in ('PLAN_EPARGNE_POPULAIRE', ):
                    return True

    @method
    class iter_subscription(DictElement):
        item_xpath = 'donnees/syntheseParGroupeProduit/*/prestations'

        class item(ItemElement):
            klass = Subscription

            obj_id = CleanText(Dict('numeroCompteFormate'), replace=[(' ', '')])
            obj_subscriber = Env('subscriber')
            obj_label = Format('%s %s', Dict('labelToDisplay'), Field('id'))
            obj__internal_id = Dict('idTechnique')
            obj__is_card = False

    @method
    class iter_subscription_cards(DictElement):
        item_xpath = 'donnees/syntheseParGroupeProduit/*/prestations/*/cartes'

        class item(ItemElement):
            klass = Subscription

            obj_id = CleanText(Dict('numeroCompteFormate'), replace=[(' ', '')])
            obj_subscriber = Env('subscriber')
            obj_label = Format('%s %s', Dict('labelToDisplay'), Field('id'))
            obj__internal_id = Dict('idTechnique')
            obj__is_card = True

class RevolvingDetailsPage(LoggedPage, JsonPage):
    def get_revolving_rate(self, account):
        # If there are no available details for the loan, the statut will be "NOK"
        if Dict('commun/statut')(self.doc) == 'NOK':
            return
        else:
            # There is no default value in the Coalesce because we want it to crash in case of
            # unknown value to be able to add it
            rate = Coalesce(
                Dict('donnees/caracteristiquesReservea/tauxHorsAssurance', NotAvailable),
                Dict('donnees/caracteristiquesCreditConfiance/taux', NotAvailable),
            )(self.doc)

            account.rate = CleanDecimal().filter(rate)


class LoansPage(JsonBasePage):
    def get_loan_details(self, loan):
        loan_types_fields = ('creditImmo', 'creditConsoAmortissable', 'creditConsoRenouvelable')

        for loan_type in loan_types_fields:
            for acc in Dict(f'donnees/{loan_type}')(self.doc):
                if CleanText(Dict('detailPret/idPrestation'))(acc) == loan._prestation_id:
                    loan.currency = Currency(Dict('currency'))(acc)
                    loan.next_payment_amount = CleanDecimal.French(Dict('montantProchaineEcheance'))(acc)
                    loan.next_payment_date = Date(CleanText(Dict('detailPret/dateProchaineEcheance'), default=NotAvailable), default=NotAvailable)(acc)
                    loan.used_amount = CleanDecimal.French(Dict('montantUtilise', default=None), default=NotAvailable)(acc)
                    loan.subscription_date = Date(CleanText(Dict('detailPret/dateOuverture'), default=''), default=NotAvailable)(acc)
                    loan.available_amount = CleanDecimal.French(Dict('soldeReserveOuCapital', default=None), default=NotAvailable)(acc)
                    loan.balance = CleanDecimal.French(
                        Coalesce(
                            Dict('capitalRestantDu', default=NotAvailable),
                            Dict('montantUtilise', default=NotAvailable),
                        ),
                        sign='-',
                    )(acc)

                    loan.total_amount = CleanDecimal.French(
                        Coalesce(
                            Dict('montantPret', default=NotAvailable),
                            Dict('plafond', default=NotAvailable),
                    ))(acc)

                    loan.duration = Eval(int, CleanText(
                        Dict('detailPret/dureeInitialePret'),
                     ))(acc)

                    loan.maturity_date = Date(
                        CleanText(
                            Dict('detailPret/dateFinPret', default=''),
                            default=NotAvailable,
                        ),
                        default=NotAvailable,
                    )(acc)

                    loan.rate = CleanDecimal.French(
                        Dict("tauxClient", default=NotAvailable),
                        default=NotAvailable,
                    )(acc)

                    loan._loan_parent_id = Regexp(
                        Coalesce(
                            CleanText(Dict('detailPret/comptePrelevement1', default=''), default=NotAvailable),
                            CleanText(Dict('detailPret/comptePrelevement2', default=''), default=NotAvailable),
                            default=NotAvailable,
                        ),
                        r'^.{5}(\d+)',
                        default=NotAvailable,
                    )(acc)


class Transaction(FrenchTransaction):
    PATTERNS = [(re.compile(r'^CARTE \w+ RETRAIT DAB.*? (?P<dd>\d{2})\/(?P<mm>\d{2})( (?P<HH>\d+)H(?P<MM>\d+))? (?P<text>.*)'),
                                                            FrenchTransaction.TYPE_WITHDRAWAL),
                (re.compile(r'^CARTE \w+ (?P<dd>\d{2})\/(?P<mm>\d{2})( A (?P<HH>\d+)H(?P<MM>\d+))? RETRAIT DAB (?P<text>.*)'),
                                                            FrenchTransaction.TYPE_WITHDRAWAL),
                (re.compile(r'^CARTE \w+ REMBT (?P<dd>\d{2})\/(?P<mm>\d{2})( A (?P<HH>\d+)H(?P<MM>\d+))? (?P<text>.*)'),
                                                            FrenchTransaction.TYPE_PAYBACK),
                (re.compile(r'^(?P<category>CARTE) \w+ (?P<dd>\d{2})\/(?P<mm>(0[1-9]|1[0-2])) (?P<text>.*)'),
                                                            FrenchTransaction.TYPE_CARD),
                (re.compile(r'^(?P<dd>\d{2})(?P<mm>\d{2})\/(?P<text>.*?)\/?(-[\d,]+)?$'),
                                                            FrenchTransaction.TYPE_CARD),
                (re.compile(r'^(?P<category>(COTISATION|PRELEVEMENT|TELEREGLEMENT|TIP)) (?P<text>.*)'),
                                                            FrenchTransaction.TYPE_ORDER),
                (re.compile(r'^(\d+ )?VIR (PERM )?POUR: (.*?) (REF: \d+ )?MOTIF: (?P<text>.*)'),
                                                            FrenchTransaction.TYPE_TRANSFER),
                (re.compile(r'^(?P<category>VIR(EMEN)?T? \w+) (?P<text>.*)'),
                                                            FrenchTransaction.TYPE_TRANSFER),
                (re.compile(r'^(CHEQUE) (?P<text>.*)'),     FrenchTransaction.TYPE_CHECK),
                (re.compile(r'^REMISE CHEQUE (?P<text>.*)'),
                                                            FrenchTransaction.TYPE_CHECK),
                (re.compile(r'^(FRAIS) (?P<text>.*)'),      FrenchTransaction.TYPE_BANK),
                (re.compile(r'^(?P<category>ECHEANCEPRET)(?P<text>.*)'),
                                                            FrenchTransaction.TYPE_LOAN_PAYMENT),
                (re.compile(r'^(?P<category>REMISE CHEQUES)(?P<text>.*)'),
                                                            FrenchTransaction.TYPE_DEPOSIT),
                (re.compile(r'^CARTE RETRAIT (?P<text>.*)'),
                                                            FrenchTransaction.TYPE_WITHDRAWAL),
                (re.compile(r'^TOTAL DES FACTURES (?P<text>.*)'),
                                                            FrenchTransaction.TYPE_CARD_SUMMARY),
                (re.compile(r'^DEBIT MENSUEL CARTE (?P<text>.*)'),
                                                            FrenchTransaction.TYPE_CARD_SUMMARY),
                (re.compile(r'^CREDIT MENSUEL CARTE (?P<text>.*)'),
                                                            FrenchTransaction.TYPE_CARD_SUMMARY),
                (re.compile(r'^Paiements CB (?P<text>.*)'),
                                                            FrenchTransaction.TYPE_CARD_SUMMARY),
                (re.compile(r'^CARTE \w+ (?P<dd>\d{2})\/(?P<mm>(0[1-9]|1[0-2])) (?P<text>.*)'),
                                                            FrenchTransaction.TYPE_CARD),
               ]


_OUTGOING_TRANSFER_TOKENS = ('POUR', 'REF', 'MOTIF', 'CHEZ')
_OUTGOING_TRANSFER_SPLIT_RE = f"({'|'.join(_OUTGOING_TRANSFER_TOKENS)}): (?!(?:{'|'.join(_OUTGOING_TRANSFER_TOKENS)}):)"


def parse_outgoing_transfer_transaction(line: str | None) -> dict[str, str | IBAN]:
    """Extract transfer transaction data.

    Examples:
        # Transfer to another account of the same bank
        >>> parse_outgoing_transfer_transaction(
        ...     "000001 VIR EUROPEEN EMIS LOGITEL "
        ...     "POUR: M JOHN DOE 24 12 SG 01234 CPT 00012345679 "
        ...     "REF: 1234567890123 "
        ...     "MOTIF: Epargne "
        ...     "CHEZ: SOGEFRPP"
        ... )  # doctest: +NORMALIZE_WHITESPACE
        {'POUR': 'M JOHN DOE',
         'REF': '1234567890123',
         'MOTIF': 'Epargne',
         'CHEZ': 'SOGEFRPP',
         'IBAN': <IBAN=FR7630003012340001234567951>}

        # Euro zone transfer
        >>> parse_outgoing_transfer_transaction(
        ...   "000001 VIR EUROPEEN EMIS LOGITEL "
        ...   "POUR: John Doe "
        ...   "REF: 1234567890123 "
        ...   "CHEZ: NTSBDEB1"  # N26
        ... )  # doctest: +NORMALIZE_WHITESPACE
        {'POUR': 'John Doe',
         'REF': '1234567890123',
         'MOTIF': NotAvailable,
         'CHEZ': 'NTSBDEB1',
         'IBAN': NotAvailable}

        # French bank transfer
        >>> parse_outgoing_transfer_transaction(
        ...     "000001 VIR EUROPEEN EMIS LOGITEL "
        ...     "POUR: RENT AGENCY "
        ...     "30 12 BQ 3000401234 CPT 00012345678 "
        ...     "REF: 1234567890123 "
        ...     "MOTIF: Loyer "
        ...     "CHEZ: BNPAFRPP"
        ... )  # doctest: +NORMALIZE_WHITESPACE
        {'POUR': 'RENT AGENCY',
         'REF': '1234567890123',
         'MOTIF': 'Loyer',
         'CHEZ': 'BNPAFRPP',
         'IBAN': <IBAN=FR7630004012340001234567862>}
    """
    # intraday tr have libOpeComplet set to None
    # future tr do not have libOpeComplet field
    if line is None:
        return {}

    res = re.split(_OUTGOING_TRANSFER_SPLIT_RE, line)
    if res.count("POUR") == 0:
        return {}

    tr_data = {token: NotAvailable for token in _OUTGOING_TRANSFER_TOKENS}
    tr_data.update(
        {
            token: data.strip()
            for token, data in zip(res[1::2], res[2::2])
        }
    )

    if m := re.search(
        r"(?P<recipient>.+) (?P<day>\d{2}) (?P<month>\d{2}) "
        r"(?:SG (?P<branchid>\d+)|BQ (?P<bankid>\d+)) CPT (?P<acctid>\d+)",
        tr_data["POUR"],
    ):
        tr_data['POUR'] = m['recipient']

        bic = BIC(tr_data["CHEZ"])
        tr_data["IBAN"] = IBAN.generate(
            bic.country_code,
            bic.country_bank_code if m["branchid"] else m["bankid"],
            m["acctid"],
            m["branchid"] or "",
        )
    else:
        tr_data["IBAN"] = NotAvailable

    return tr_data


class TransactionItemElement(ItemElement):
    klass = Transaction

    def parse(self, el: ItemElement) -> None:
        """Prepare multiple Transaction fields at once."""
        # Break down libMotifVirementOuPrelevement in useful metadata.
        # Some instances of incoming transfers do not hold REF even through it is present in libOpeComplet.
        # Example value:
        #   - SEPA payment: <TEXT> REF: <REF> MANDAT <SEPA_MANDATE_ID>
        #   - Incoming transfer: <TEXT>
        motif_raw = Dict('libMotifVirementOuPrelevement')(self)
        if motif_raw:
            self.env.update(
                dict(
                    zip_longest(
                        ("motive", "ref", "sepa_mandate"),
                        re.split('(?: (?:REF:|MANDAT) )', motif_raw)
                    )
                )
            )

        # When a loan payment transaction is found, extract data into a Loan object
        # for browser and a separate loan_payment Env entry for the benefit of
        # OFX export.
        m = re.search(
            r"^ECHEANCE PRET N°(?P<loan_id>\d+)"
            r"(?: CAPITAL AMORTI : (?P<principal_amount>(?:\d+ )*\d+(?:,\d+)?))?"
            r"(?: INTERETS : (?P<interest_amount>(?:\d+ )*\d+(?:,\d+)?))?"
            r"(?: ASSURANCE : (?P<insurance_amount>(?:\d+ )*\d+(?:,\d+)?))?"
            r"(?: CAPITAL RESTANT : (?P<principal_balance>(?:\d+ )*\d+(?:,\d+)?))?"
            r"(?: DATE PREVISIONNELLE DE FIN : (?P<maturity_date>.*))?",
            Dict("libOpe")(el),
        )
        if m:
            loan_data = m.groupdict()
            loan_data.update(
                {
                    (
                        key,
                        CleanDecimal.French().filter(m[key])
                        if m[key]
                        else NotAvailable,
                    )
                    for key in (
                        "principal_amount",
                        "interest_amount",
                        "insurance_amount",
                        "principal_balance",
                    )
                }
            )
            loan = Loan(m["loan_id"])
            loan.last_payment_amount = Field("amount")(self)
            loan.last_payment_date = Field("date")(self)
            loan.insurance_amount = loan_data["insurance_amount"]
            loan.maturity_date = m["maturity_date"]

            self.env["loan"] = loan
            self.env["loan_payment"] = loan_data

        # Extract transfer account data. To be used in OFX export.
        # TODO: parse according to Field("type")
        m = parse_outgoing_transfer_transaction(Dict("libOpeComplet")(self))
        if m:
            # Accounts managed by the owner automatically appear in transfer allow list.
            for recipient in self.env.get("transfer_recipients", []):
                if recipient.label.casefold() == m["POUR"].casefold() or recipient.iban == m["IBAN"]:
                    self.logger.info("Transaction is sending funds to %s", m["POUR"])
                    self.env["transfer_account"] = recipient
                    break
            else:
                # Fallback for multi-owner accounts
                self.logger.debug("Recipient %s not found in beneficiary list. (%s)", m["POUR"], el)
                recipient = Recipient()
                recipient.iban = m["IBAN"]
                recipient.id = str(m["IBAN"])
                recipient.label = m["POUR"]
                # On societe generale recipients are immediatly available.
                recipient.enabled_at = datetime.datetime.now().replace(microsecond=0)
                recipient.currency = u'EUR'
                recipient.bank_name = recipient.iban.bank_name
                self.env["transfer_account"] = recipient

        return

    def obj_id(self):
        # real transaction id is like:
        # <transaction_id>/DDMMYYYY/<internal_id>
        if not Dict('idOpe')(self) or Regexp(CleanText(Dict('idOpe')), r'^(\d+)$', default=NotAvailable)(self):
            return ''
        id_op = Regexp(CleanText(Dict('idOpe')), r'(\w+)/')(self)
        if id_op not in ['0', 'null']:
            # card summary has transaction id '0'
            return id_op

    def obj_vdate(self):
        if Dict('dateChargement')(self):
            return Eval(lambda t: datetime.date.fromtimestamp(int(t)/1000),Dict('dateChargement'))(self)

    def obj__memo(self):
        memo = Env("motive", NotAvailable)(self)
        sepa_mandate = Env("sepa_mandate", NotAvailable)(self)
        if memo and sepa_mandate:
            memo += " MANDAT " + sepa_mandate
        return memo

    obj_date = Eval(lambda t: datetime.date.fromtimestamp(int(t)/1000), Dict('dateOpe'))
    obj_amount = CleanDecimal(Dict('mnt'))
    obj_raw = Transaction.Raw(Dict('libOpe'))

    obj__loan = Env("loan", NotAvailable)  # Loan account. Used in browser.
    obj__loan_payment = Env("loan_payment", NotAvailable)  # Loan payment information.
    obj__ref = Env("ref", NotAvailable)
    obj__transfer_account = Env("transfer_account", default=NotAvailable)


class HistoryPage(JsonBasePage):
    """
    be carefull : `transaction_klass` is used in another page
    of an another module which is an abstract of this page
    """
    transaction_klass = Transaction

    def hist_pagination(self, condition):
        all_conditions = {
            'history': (
                not Dict('donnees/listeOperations', default=None)(self.doc),
                not Dict('donnees/recapitulatifCompte/chargerPlusOperations', default=None)(self.doc)
            ),
            'future': (
                not Dict('donnees/listeOperationsFutures', default=None)(self.doc),
                not Dict('donnees/recapitulatifCompte/chargerPlusOperations', default=None)(self.doc)
            ),
            'intraday': (
                not Dict('donnees/listeOperations', default=None)(self.doc),
                Dict('donnees/listeOperations', default=None)(self.doc) and \
                    not Dict('donnees/listeOperations/0/statutOperation', default=None)(self.doc) == 'INTRADAY',
                not Dict('donnees/recapitulatifCompte/chargerPlusOperations', default=None)(self.doc),
                not Dict('donnees/recapitulatifCompte/encours', default=None)(self.doc),
            ),
        }

        if any(all_conditions[condition]):
            return

        if '&an200_operationsSupplementaires=true' in self.browser.url:
            return self.browser.url
        return self.browser.url + '&an200_operationsSupplementaires=true'

    @pagination
    @method
    class iter_history(DictElement):
        def condition(self):
            # If we reach this point and it's "NOK", that's mean it's a known error handled
            # in JsonBasePage and we can't have history for now.
            return Dict('commun/statut')(self.el).upper() != 'NOK'

        item_xpath = 'donnees/listeOperations'

        class item(TransactionItemElement):
            def condition(self):
                return Dict('statutOperation')(self) == 'COMPTABILISE'

    @pagination
    @method
    class iter_card_transactions(DictElement):
        item_xpath = 'donnees/listeOperations'

        class item(TransactionItemElement):
            def condition(self):
                # card summary transaction id is like:
                # 0/DDMMYYYY/<internal_id>
                conditions = (
                    Dict('idOpe')(self) and \
                        Regexp(CleanText(Dict('idOpe')), r'(\w+)/', default=NotAvailable)(self) in ['0', 'null'],
                    Env('card_number')(self) in Dict('libOpe')(self),
                    Dict('statutOperation')(self) == 'COMPTABILISE',
                )
                return all(conditions)

            obj_type = Transaction.TYPE_CARD_SUMMARY

            def obj_amount(self):
                return abs(CleanDecimal(Dict('mnt'))(self))

            class obj__card_transactions(DictElement):
                item_xpath = 'listeOpeFilles'

                class tr_item(TransactionItemElement):
                    def condition(self):
                        return Dict('statutOperation')(self) == 'COMPTABILISE'

                    obj_raw = Transaction.Raw(Dict('libOpe'))
                    obj_bdate = Eval(lambda t: datetime.date.fromtimestamp(int(t) / 1000), Dict('dateOpe'))

    @pagination
    @method
    class iter_intraday_comings(DictElement):
        def condition(self):
            # If we reach this point and it's "NOK", that mean it's a known error handled
            # in JsonBasePage and we can't have history for now.
            return Dict('commun/statut')(self.el).upper() != 'NOK'

        item_xpath = 'donnees/listeOperations'

        class item(TransactionItemElement):
            def condition(self):
                return Dict('statutOperation')(self) == 'INTRADAY'

    @pagination
    @method
    class iter_future_transactions(DictElement):
        item_xpath = 'donnees/listeOperationsFutures'

        class item(ItemElement):
            def condition(self):
                conditions = (
                    Dict('operationCategorisable')(self) in ('FUTURE', 'OPERATION_MERE'),
                    Dict('prestationIdAssocie')(self) == Env('acc_prestation_id')(self)
                )
                return all(conditions)

            klass = Transaction

            obj_date = Date(Dict('dateEcheance'))
            obj_amount = CleanDecimal(Dict('montant/value'))
            obj_raw = obj_label = Dict('libelleAAfficher')

            class obj__card_coming(DictElement):
                item_xpath = 'operationsFilles'

                class tr_item(ItemElement):
                    klass = Transaction

                    obj_amount = CleanDecimal(Dict('montant/value'))
                    obj_date = obj_vdate = obj_bdate = Date(Dict('dateEcheance'))
                    obj_raw = Transaction.Raw(Dict('libelleOrigine'))


class CardHistoryPage(LoggedPage, HTMLPage):
    @method
    class iter_card_history(ListElement):
        item_xpath = '//tr'

        class item(ItemElement):
            klass = Transaction

            obj_label = CleanText('.//td[@headers="Libelle"]/span')
            obj_type = Transaction.TYPE_DEFERRED_CARD

            def obj_date(self):
                if not 'TOTAL DES FACTURES' in Field('label')(self):
                    return Date(Regexp(CleanText('.//td[@headers="Date"]'), r'\d{2}\/\d{2}\/\d{4}'))(self)
                else:
                    return NotAvailable

            def obj_amount(self):
                if not 'TOTAL DES FACTURES' in Field('label')(self):
                    return MyDecimal(CleanText('.//td[contains(@headers, "Debit")]'))(self)
                else:
                    return abs(MyDecimal(CleanText('.//td[contains(@headers, "Debit")]'))(self))

            def obj_raw(self):
                if not 'TOTAL DES FACTURES' in Field('label')(self):
                    return CleanText('.//td[@headers="Libelle"]/span')(self)
                return NotAvailable


class CreditPage(HTMLLoggedPage):
    def get_history_url(self):
        redirection_script = CleanText('//script[contains(text(), "setPrestationURL")]')(self.doc)
        history_link = re.search(r'setPrestationURL\("(.*)"\)', redirection_script)
        if history_link:
            return history_link.group(1)

    def get_error_msg(self):
        # to be consistent with other iter_history from old website
        # not encounter yet
        pass


class CreditHistoryPage(LoggedPage, HTMLPage):
    def build_doc(self, content):
        # for some reason, lxml discards the first tag inside the CDATA
        # (of course, there shouldn't be XML inside the CDATA in the first place)
        content = content.replace(b'<![CDATA[', b'<![CDATA[<bullshit/>')
        return super(CreditHistoryPage, self).build_doc(content)

    @method
    class iter_history(ListElement):
        item_xpath = '//tr'

        class item(ItemElement):
            klass = Transaction

            obj_label = CleanText('./@title')
            obj_date = Date(CleanText('./td[@headers="Date"]'), dayfirst=True)

            def obj_amount(self):
                credit = MyDecimal(CleanText('./td[contains(@headers, "Credit")]', replace=[('&nbsp;', '')]))(self)
                if credit:
                    return credit
                return MyDecimal(CleanText('./td[contains(@headers, "Debit")]', replace=[('&nbsp;', '')]))(self)


class OldHistoryPage(HTMLLoggedPage):
    def get_history_url(self):
        redirection = CleanText('//body/@onload')(self.doc)
        history_link = re.search(r",'(/.*)',", redirection)
        if history_link:
            return history_link.group(1)

    @method
    class iter_history(TableElement):
        head_xpath = '//table[not(@id)]//td/div[contains(@class, "tableauHead")]'
        item_xpath = '//table[@id]//tr'

        def condition(self):
            no_transaction_msg = any((
                self.xpath('//div[contains(text(), "Aucune opération trouvée sur la période de restitution possible")]'),
                self.xpath('//div[contains(text(), "Aucune opération n\'a été réalisée depuis le dernier relevé")]'),
            ))
            return not no_transaction_msg

        col_label = 'Libellé'
        col_amount = 'Montant'
        col_date = 'Date'

        class item(ItemElement):
            klass = Transaction

            obj_label = CleanText(TableCell('label'))
            obj_amount = CleanDecimal(TableCell('amount'))
            obj_date = Date(CleanText(TableCell('date')), dayfirst=True)

    def get_error_msg(self):
        assert self.doc.xpath('//div[@class="error_content"]'), 'There should have link to history page.'
        return CleanText('//div[@class="error_content"]//span[@class="error_msg"]')(self.doc)


class LifeInsurance(HTMLLoggedPage):
    def on_load(self):
        errors_msg = (
            CleanText('//span[@class="error_msg"]')(self.doc),
            CleanText("//div[@class='net2g_asv_error_full_page']")(self.doc)
        )
        for error_msg in errors_msg:
            if error_msg and 'Le service est momentanément indisponible' in error_msg:
                raise BrowserUnavailable(error_msg)
            if error_msg and 'Aucune opération' in error_msg:
                break
        else:
            assert not any(errors_msg), 'Some errors are not handle yet'

    def has_link(self):
        return Link('//a[@href="asvcns20a.html"]', default=NotAvailable)(self.doc)

    def get_history_url(self):
        # The HTML div in which we get this "Suivi des opérations" link has all of its
        # text parts double encoded with latin-1 and utf-8. The rest of the page is utf-8
        # encoded only. Coalesce here in case they fix this bad encoding.
        return Coalesce(
            Link('//a[img[@alt="Suivi des opÃ©rations"]]', default=None),
            Link('//a[img[@alt="Suivi des opérations"]]', default=None),
        )(self.doc)

    def get_error_msg(self):
        # to be consistent with other iter_history from old website
        # not encounter yet
        pass

    def get_pages(self):
        pages = CleanText('//div[@class="net2g_asv_tableau_pager"]')(self.doc)
        if pages:
            # "pages" value is for example "1/5"
            return re.search(r'(\d)/(\d)', pages).group(1, 2)

    def li_pagination(self):
        pages = self.get_pages()
        if pages:
            current_page, total_pages = int(pages[0]), int(pages[1])
            if current_page < total_pages:
                data = {
                    'a100_asv_action': 'actionSuivPage',
                    'a100_asv_numPage': current_page,
                    'a100_asv_nbPages': total_pages,
                }
                return requests.Request('POST', self.browser.url, data=data)


class LifeInsuranceInvest(LifeInsurance):
    @pagination
    @method
    class iter_investment(TableElement):
        def next_page(self):
            return self.page.li_pagination()

        item_xpath = '//table/tbody/tr[starts-with(@class, "net2g_asv_tableau_ligne_")]'
        head_xpath = '//table/thead/tr/td'

        col_label = re.compile('Support')
        col_quantity = re.compile('Nombre')
        col_unitvalue = re.compile('Valeur')
        col_valuation = re.compile('Capital|Epargne')

        class item(ItemElement):
            klass = Investment

            obj_code = Regexp(CleanText(TableCell('label')), r'Code ISIN : (\w+) ', default=NotAvailable)
            obj_quantity = MyDecimal(TableCell('quantity'), default=NotAvailable)
            obj_unitvalue = MyDecimal(TableCell('unitvalue'), default=NotAvailable)
            # Valuation column for PERP invests may be "Capital" or "Epargne"
            obj_valuation = MyDecimal(TableCell('valuation', default=NotAvailable), default=NotAvailable)

            def obj_label(self):
                if 'FONDS EN EUROS' in CleanText(TableCell('label'))(self):
                    return 'FONDS EN EUROS'
                return Regexp(CleanText(TableCell('label')), r'Libellé support : (.*) Code ISIN')(self)

            def obj_code_type(self):
                if Field('label')(self) == 'FONDS EN EUROS':
                    return NotAvailable
                return Investment.CODE_TYPE_ISIN


class LifeInsuranceInvest2(LifeInsuranceInvest):
    def get_history_url(self):
        return NotAvailable

    def iter_history(self):
        # on SG website, there are no transactions for this type of account
        # there no trace on any space for the history on this page
        return []


class LifeInsuranceAPI(LoggedPage, JsonPage):
    def check_availability(self):
        return Dict('commun/statut')(self.doc) == 'OK'


class LifeInsuranceInvestAPI(LoggedPage, JsonPage):
    def check_availability(self):
        return Dict('commun/statut')(self.doc) == 'OK'

    @method
    class iter_investment(DictElement):
        item_xpath = 'donnees/actifs'

        class item(ItemElement):
            klass = Investment

            obj_label = CleanText(Dict('libelle'))
            obj_valuation = CleanDecimal.French(Dict('mntTotal/value'))
            obj_code = IsinCode(Dict('codeISIN'), default=NotAvailable)
            obj_code_type = IsinType(Field('code'))


class LifeInsuranceInvestAPI2(LoggedPage, JsonPage):
    @method
    class iter_investment(DictElement):
        item_xpath = 'donnees/actifs/*/supportList'

        class item(ItemElement):
            klass = Investment

            obj_label = CleanText(Dict('libelleSupport'))
            obj_valuation = CleanDecimal.French(Dict('montantDetenu'))
            obj_code = IsinCode(Dict('codePlacement'), default=NotAvailable)
            obj_code_type = IsinType(Field('code'))

            def obj_quantity(self):
                if Field('label')(self) == 'SUPPORT EURO':
                    return NotAvailable
                return CleanDecimal.SI(Dict('nombrePart'))(self)

            def obj_unitvalue(self):
                if Field('label')(self) == 'SUPPORT EURO':
                    return NotAvailable
                return CleanDecimal.French(Dict('coursDuPlacement'))(self)


class LifeInsuranceInvestDetailsAPI(LoggedPage, JsonPage):
    @method
    class fill_life_insurance_investment(ItemElement):
        def parse(self, el):
            for fund in Dict('donnees/listePerformancePlacements')(self):
                if Dict('codePlacement')(fund) == self.obj.code:
                    current_fund = fund
                    break
            else:
                return

            diff_ratio = CleanDecimal.SI(
                Dict('pourcentagePerformance', default=None),
                default=None
            )(current_fund)
            if not empty(diff_ratio):
                self.env['diff_ratio'] = diff_ratio / 100
            else:
                self.env['diff_ratio'] = NotAvailable

            self.env['diff'] = CleanDecimal.SI(Dict('montantPlusMoinsValue'))(current_fund)
            self.env['unitprice'] = CleanDecimal.SI(Dict('prixDeRevient'))(current_fund)
            self.env['vdate'] = Date(CleanText(Dict('donnees/datePerformance')))(self)

        def condition(self):
            return self.obj.code

        obj_unitprice = Env('unitprice')
        obj_diff = Env('diff')
        obj_diff_ratio = Env('diff_ratio')
        obj_vdate = Env('vdate')


class LifeInsuranceHistory(LifeInsurance):
    @pagination
    @method
    class iter_history(TableElement):
        def next_page(self):
            return self.page.li_pagination()

        item_xpath = '//table/tbody/tr[starts-with(@class, "net2g_asv_tableau_ligne_")]'
        head_xpath = '//table/thead/tr/td'

        col_label = 'Opération'
        col_date = 'Date'
        col_amount = 'Montant'
        col__status = 'Statut'

        class item(ItemElement):
            def condition(self):
                return (CleanText(TableCell('_status'))(self) == 'Réalisé' and
                        MyDecimal(TableCell('amount'), default=NotAvailable)(self))

            klass = Transaction

            obj_label = CleanText(TableCell('label'))
            obj_amount = MyDecimal(TableCell('amount'))

            def obj_date(self):
                tr_date = CleanText(TableCell('date'))(self)
                if len(tr_date) == 4:
                    # date of transaction with label 'Intérêts crédités au cours de l'année'
                    # is only year valuation
                    # set transaction date to the last day year
                    return datetime.date(int(tr_date), 12, 31)
                return Date(dayfirst=True).filter(tr_date)


class MarketPage(HTMLLoggedPage):
    def get_dropdown_menu(self):
        # Get the 'idCptSelect' in a drop-down menu that corresponds the current account
        return Attr('//select[@id="idCptSelect"]//option[@value and @selected="selected"]', 'value')(self.doc)

    def get_pages(self):
        several_pages = CleanText('//tr[td[contains(@class,"TabTit1l")]][count(td)=3]')(self.doc)
        if several_pages:
            # "several_pages" value is "1/5" for example
            return re.search(r'(\d+)/(\d+)', several_pages).group(1, 2)

    def get_market_order_link(self):
        return Link('//a[contains(text(), "Suivi des ordres")]', default=None)(self.doc)

    def market_pagination(self):
        # Next page is handled by js. Need to build the right url by changing params in current url
        several_pages = self.get_pages()
        if several_pages:
            current_page, total_pages = map(int, several_pages)
            if current_page < total_pages:
                params = {
                    'action': 11,
                    'idCptSelect': self.get_dropdown_menu(),
                    'numPage': current_page + 1,
                }
                url_to_keep = urlsplit(self.browser.url)[:3]
                url_to_complete = (urlencode(params), '')  # '' is the urlsplit().fragment needed for urlunsplit
                next_page_url = urlunsplit(url_to_keep + url_to_complete)
                return next_page_url

    @pagination
    @method
    class iter_investments(TableElement):
        def next_page(self):
            return self.page.market_pagination()

        table_xpath = '//tr[td[contains(@class,"TabTit1l")]]/following-sibling::tr//table'
        head_xpath = table_xpath + '//tr[1]/td'
        item_xpath = table_xpath + '//tr[position()>1]'

        col_label = 'Valeur'
        col_quantity = 'Quantité'
        col_valuation = 'Evaluation'
        col_vdate = 'Date'
        col_unitvalue = 'Cours'

        def condition(self):
            return not 'PAS DE VALEURS DETENUES ACTUELLEMENT SUR CE COMPTE' in \
                CleanText('//td[@class="MessErreur"]')(self.el)

        class item(ItemElement):
            def condition(self):
                return self.xpath('./td[not(@colspan) and contains(@class, "TabCelLeft")]')

            klass = Investment

            def obj_label(self):
                return CleanText(TableCell('label')(self)[0].xpath('.//text()'))(self)

            obj_quantity = MyDecimal(TableCell('quantity'))
            obj_valuation = MyDecimal(TableCell('valuation'))
            obj_vdate = Date(Regexp(CleanText(TableCell('vdate')), r'(\d{2}/\d{2}/\d{4})'))
            obj_unitvalue = MyDecimal(TableCell('unitvalue'))

            def obj_code(self):
                matches = re.findall(r'\w+', CleanText(TableCell('label')(self)[0].xpath('.//@title'))(self))
                for match in matches:
                    code = IsinCode(default=None).filter(match)
                    if code:
                        return code
                return NotAvailable

            def obj_code_type(self):
                matches = re.findall(r'\w+', CleanText(TableCell('label')(self)[0].xpath('.//@title'))(self))
                for match in matches:
                    code_type = IsinType(default=None).filter(match)
                    if code_type:
                        return code_type
                return NotAvailable


class PeaLiquidityPage(LoggedPage, HTMLPage):
    def iter_investments(self, account):
        yield (create_french_liquidity(account.balance))


MARKET_ORDER_DIRECTIONS = {
    'Achat': MarketOrderDirection.BUY,
    'Vente': MarketOrderDirection.SALE,
}

MARKET_ORDER_TYPES = {
    'marché': MarketOrderType.MARKET,
    'limit': MarketOrderType.LIMIT,
    'déclenchement': MarketOrderType.TRIGGER,
}

MARKET_ORDER_PAYMENTS = {
    'Comptant': MarketOrderPayment.CASH,
}


class MarketOrderPage(LoggedPage, HTMLPage):
    def has_no_market_order(self):
        return CleanText('//div[@class="Error" and contains(text(), "Vous n\'avez aucun ordre en cours")]')(self.doc)

    def orders_unavailable(self):
        return CleanText('//div[@class="Error" and contains(text(), "Liste des ordres indisponible")]')(self.doc)

    def get_dropdown_menu(self):
        # Get the 'idCptSelect' in a drop-down menu that corresponds the current account
        return Attr('//select[@id="idCptSelect"]//option[@value and @selected="selected"]', 'value')(self.doc)

    def get_pages(self):
        several_pages = CleanText('//td[@class="TabTit1lActif"]')(self.doc)
        if several_pages:
            # "several_pages" value is "1/5" for example
            return int(re.search(r'(\d+)/(\d+)', several_pages).group(2))
        return 1

    @method
    class iter_market_orders(TableElement):
        table_xpath = '//tr[td[contains(@class,"TabTit1l")]]/following-sibling::tr//table'
        head_xpath = table_xpath + '//tr[1]/td'
        item_xpath = table_xpath + '//tr[position()>1]'

        col_label = 'Valeur'
        col_code = 'Code'
        col_direction = 'Sens'
        col_date = 'Date'
        col_state = 'Etat'

        class item(ItemElement):
            klass = MarketOrder

            obj_label = CleanText(TableCell('label'))
            obj_url = Base(TableCell('label'), Link('.//a', default=None))
            obj_code = IsinCode(CleanText(TableCell('code')), default=NotAvailable)
            obj_state = CleanText(TableCell('state'))
            obj_date = Date(CleanText(TableCell('date')), dayfirst=True)
            obj_direction = MapIn(
                CleanText(TableCell('direction')),
                MARKET_ORDER_DIRECTIONS,
                MarketOrderDirection.UNKNOWN
            )


class MarketOrderDetailPage(LoggedPage, HTMLPage):
    @method
    class fill_market_order(ItemElement):
        obj_id = Regexp(CleanText('//td[has-class("TabTit1l") and contains(text(), "Ordre")]'), r'Ordre N° (.+?) passé')
        obj_order_type = MapIn(
            Lower('//td[contains(text(), "Type de l\'ordre")]//following-sibling::td[1]'),
            MARKET_ORDER_TYPES,
            MarketOrderType.UNKNOWN
        )
        obj_execution_date = Date(
            CleanText('//td[contains(text(), "Date d\'exécution")]//following-sibling::td[1]'),
            dayfirst=True,
            default=NotAvailable
        )
        obj_quantity = CleanDecimal.French(
            '//td[contains(text(), "Quantité demandée")]//following-sibling::td[1]',
            default=NotAvailable
        )
        obj_ordervalue = CleanDecimal.French(
            '//td[contains(text(), "Cours limite")]//following-sibling::td[1]',
            default=NotAvailable
        )
        obj_amount = CleanDecimal.French(
            '//td[contains(text(), "Montant")]//following-sibling::td[1]',
            default=NotAvailable
        )
        obj_unitprice = CleanDecimal.French(
            '//td[contains(text(), "Cours d\'exécution")]//following-sibling::td[1]',
            default=NotAvailable
        )
        # Extract currency & stock_market from string like 'Achat en USD sur NYSE'
        obj_currency = Currency(
            Regexp(
                CleanText('//td[contains(@class, "TabTit1l")][contains(text(), "Achat") or contains(text(), "Vente")]'),
                r'en (\w+) sur',
                default=''
            ),
            default=NotAvailable
        )
        obj_stock_market = Regexp(
            CleanText('//td[contains(@class, "TabTit1l")][contains(text(), "Achat") or contains(text(), "Vente")]'),
            r'en .* sur (\w+)$',
            default=NotAvailable
        )
        obj_payment_method = Map(
            CleanText('//td[contains(text(), "Règlement")]//following-sibling::td[1]'),
            MARKET_ORDER_PAYMENTS,
            MarketOrderPayment.UNKNOWN
        )


class AdvisorPage(LoggedPage, XMLPage):
    ENCODING = 'ISO-8859-15'

    def get_advisor(self):
        advisor = Advisor()
        advisor.name = Format('%s %s', CleanText('//NomConseiller'), CleanText('//PrenomConseiller'))(self.doc)
        advisor.phone = CleanText('//NumeroTelephone')(self.doc)
        advisor.agency = CleanText('//liloes')(self.doc)
        advisor.address = Format('%s %s %s',
                                 CleanText('//ruadre'),
                                 CleanText('//cdpost'),
                                 CleanText('//loadre')
                                 )(self.doc)
        advisor.email = CleanText('//Email')(self.doc)
        advisor.role = "wealth" if "patrimoine" in CleanText('//LibelleNatureConseiller')(self.doc).lower() else "bank"
        yield advisor


class HTMLProfilePage(HTMLLoggedPage):
    def on_load(self):
        msg = CleanText('//div[@id="connecteur_partenaire"]', default='')(self.doc) or \
              CleanText('//body', default='')(self.doc)
        service_unavailable_msg = CleanText('//div[contains(@class, "error")]//span[contains(text(), "indisponible")]')(self.doc)

        if 'Erreur' in msg:
            raise BrowserUnavailable(msg)
        if service_unavailable_msg:
            raise ProfileMissing(service_unavailable_msg)

    def get_profile(self):
        profile = Person()
        profile.name = Regexp(CleanText('//div[@id="dcr-conteneur"]//div[contains(text(), "PROFIL DE")]'), r'PROFIL DE (.*)')(self.doc)
        profile.address = CleanText('//div[@id="dcr-conteneur"]//div[contains(text(), "ADRESSE")]/following::table//tr[3]/td[2]')(self.doc)
        profile.address += ' ' + CleanText('//div[@id="dcr-conteneur"]//div[contains(text(), "ADRESSE")]/following::table//tr[5]/td[2]')(self.doc)
        profile.address += ' ' + CleanText('//div[@id="dcr-conteneur"]//div[contains(text(), "ADRESSE")]/following::table//tr[6]/td[2]')(self.doc)
        profile.country = CleanText('//div[@id="dcr-conteneur"]//div[contains(text(), "ADRESSE")]/following::table//tr[7]/td[2]')(self.doc)
        profile.email = CleanText('//span[@id="currentEmail"]')(self.doc)

        return profile


class UnavailableServicePage(LoggedPage, HTMLPage):
    def on_load(self):
        conditions = (
            self.doc.xpath('//div[contains(@class, "erreur_404_content")]'),
            'Site momentanément indisponible' in CleanText('//h2[contains(@class, "error-page")]')(self.doc),
            'momentanément indisponible' in CleanText('//div[@class="hero_container"]//h1')(self.doc),
        )

        if any(conditions):
            raise BrowserUnavailable()
