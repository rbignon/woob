# -*- coding: utf-8 -*-

# Copyright(C) 2012-2019  Budget Insight
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
from decimal import Decimal

from datetime import date, datetime

from woob.browser.elements import method, DictElement, ItemElement, TableElement
from woob.browser.filters.html import Attr, TableCell, HasElement
from woob.browser.filters.json import Dict
from woob.browser.filters.standard import (
    CleanText, CleanDecimal, Currency, Eval, Env, Map, MapIn,
    Format, Field, Lower, Regexp, Date,
)
from woob.browser.pages import HTMLPage, LoggedPage, JsonPage, pagination
from woob.capabilities.bank import Account
from woob.capabilities.base import NotAvailable, empty
from woob.capabilities.profile import Person
from woob.capabilities.wealth import Investment
from woob.tools.capabilities.bank.investments import IsinCode, IsinType
from woob.tools.capabilities.bank.transactions import FrenchTransaction
from woob.tools.date import parse_french_date


def float_to_decimal(f):
    if empty(f):
        return NotAvailable
    return Decimal(str(f))

class RootPage(HTMLPage):
    def is_website_unavailable(self):
        return HasElement('//head/title[text()="Site temporairement indisponible"]')(self.doc)

class LoginPage(HTMLPage):
    def get_vk_password(self, password):
        # The virtual keyboard is a table with cells containing the VK's
        # displayed number and JS code with the transformed number
        # <td id="hoverable" class="hoverable" onclick="appendTextInputCalculator(0, 'password')" >5</td>

        vk_dict = {}
        for vk_cell in self.doc.xpath('//table[@id="calculator"]//td'):
            vk_dict[CleanText('.')(vk_cell)] = Regexp(Attr('.', 'onclick'), r"\((\d), 'password'\)")(vk_cell)
        return ''.join(vk_dict[char] for char in password)

    def login(self, username, password):
        form = self.get_form()
        form['username'] = username
        form['password'] = self.get_vk_password(password)
        form.submit()

    def has_strong_authentication(self):
        return CleanText('//h4[contains(text(), "Connexion sécurisée par SMS")]')(self.doc)

    def get_error_message(self):
        return CleanText('//div[@id="modal"]//div[@class="gpm-modal-header"]')(self.doc)


class HomePage(LoggedPage, HTMLPage):
    pass


class Transaction(FrenchTransaction):
    PATTERNS = [
        (re.compile(r'^(VIR DE|Vir à|Virement) (?P<text>.*)'), FrenchTransaction.TYPE_TRANSFER),
        (re.compile(r'^Versement (?P<text>.*)'), FrenchTransaction.TYPE_TRANSFER),
        (re.compile(r'^CHEQUE'), FrenchTransaction.TYPE_CHECK),
        (re.compile(r'^(Prl de|Prlv) (?P<text>.*)'), FrenchTransaction.TYPE_ORDER),
        (re.compile(r'^(Ech.|Echéance) (?P<text>.*)'), FrenchTransaction.TYPE_LOAN_PAYMENT),
        (re.compile(r'^Regl Impayé prêt'), FrenchTransaction.TYPE_LOAN_PAYMENT),
        (re.compile(r'^Frais tenue de compte'), FrenchTransaction.TYPE_BANK),
        (re.compile(r'^(Cotis|Cotisation) (?P<text>.*)'), FrenchTransaction.TYPE_BANK),
        (re.compile(r'^(Int |Intérêts)'), FrenchTransaction.TYPE_BANK),
        (re.compile(r'^Régularisation'), FrenchTransaction.TYPE_BANK),
        (re.compile(r'^Prélèvement'), FrenchTransaction.TYPE_BANK),
        (re.compile(r'^Commission'), FrenchTransaction.TYPE_BANK),
        (re.compile(r'^Facture (?P<dd>\d{2})/(?P<mm>\d{2}) - (?P<text>.*)'), FrenchTransaction.TYPE_CARD),
        (re.compile(r'(?P<dd>\d{2})/(?P<mm>\d{2}) - (?P<text>.*) Paiement carte'),
         FrenchTransaction.TYPE_CARD),
        (re.compile(r'(?P<dd>\d{2})/(?P<mm>\d{2}) - (?P<text>.*) Retrait carte'),
         FrenchTransaction.TYPE_WITHDRAWAL),
        (re.compile(r'(?P<dd>\d{2})/(?P<mm>\d{2}) - (?P<text>.*) Rembt carte'),
         FrenchTransaction.TYPE_PAYBACK),
    ]


ACCOUNT_TYPES = {
    'compte bancaire': Account.TYPE_CHECKING,
    'epargne bancaire': Account.TYPE_SAVINGS,
    'crédit': Account.TYPE_LOAN,
    'epargne': Account.TYPE_LIFE_INSURANCE,
    'objectif retraite': Account.TYPE_LIFE_INSURANCE,
    'retraite active': Account.TYPE_LIFE_INSURANCE,
    'nouvelle vie': Account.TYPE_LIFE_INSURANCE,
    'perp': Account.TYPE_PERP,
    'pee': Account.TYPE_PEE,
    'madelin': Account.TYPE_MADELIN,
    'retraite pro': Account.TYPE_MADELIN,
    'compte titres': Account.TYPE_MARKET,
    'certificat mutualiste': Account.TYPE_MARKET,
}


class AccountsPage(LoggedPage, JsonPage):
    @method
    class iter_accounts(DictElement):
        item_xpath = 'syntheseContrats/entries/*/entries'

        class iter_items(DictElement):
            item_xpath = 'contratItems'

            def parse(self, el):
                type_ = Dict('libelle')(self)
                # `Certificat mutualiste` used to be a category
                # Now it's categorized as 'Epargne' but not treated like other 'Epargne' accounts
                if type_ == 'Epargne' and Dict('code')(self) == 'F_C_MUTUALISTE':
                    type_ = 'Certificat mutualiste'
                self.env['type'] = type_

            class item(ItemElement):
                klass = Account

                def condition(self):
                    # Skip insurances, accounts that are cancelled or replaced,
                    # and accounts that have no available detail
                    return not (
                        Dict('contrat/resilie')(self) or
                        Dict('contrat/remplace')(self) or
                        not Dict('debranchement/hasDetail')(self) or (
                            Dict('contrat/produit/categorie')(self) == 'ASSURANCE'
                            and Dict('contrat/produit/famille')(self) != 'C_MUTUALISTE'
                        )
                    )

                obj_id = Dict('contrat/identifiant')
                obj_number = obj_id
                # No IBAN available for now
                obj_iban = NotAvailable
                obj_label = CleanText(Dict('contrat/produit/libelle'))
                obj_opening_date = Eval(lambda t: datetime.fromtimestamp(int(t) / 1000), Dict('contrat/dateEffet'))
                obj__category = Env('type')
                obj__product_code = CleanText(Dict('contrat/produit/code'))
                obj__url = Dict('debranchement/url', default= NotAvailable)

                def obj_type(self):
                    if Env('type')(self) in ('Retraite', 'Autre'):
                        # These two categories may contain various account types
                        return MapIn(Lower(Field('label')), ACCOUNT_TYPES, Account.TYPE_UNKNOWN)(self)
                    return Map(Lower(Env('type')), ACCOUNT_TYPES, Account.TYPE_UNKNOWN)(self)


class AccountDetailsPage(LoggedPage, JsonPage):
    @method
    class fill_account(ItemElement):
        obj_balance = CleanDecimal.US(
            Format('%s%s', Dict('contrat/signeSolde'), Eval(float_to_decimal, Dict('contrat/solde')))
        )
        obj_currency = Currency(Dict('contrat/devise'))

    @method
    class fill_loan(ItemElement):
        obj_balance = Eval(lambda x: float_to_decimal(-x), Dict('contrat/solde'))
        obj_currency = Currency(Dict('contrat/devise'))

    @method
    class fill_wealth_account(ItemElement):
        # Some accounts simply don't have any available balance...
        obj_balance = Eval(float_to_decimal, Dict('contrat/montantEpargneContrat', default=None))
        obj_currency = 'EUR'
        # The valuation_diff_ratio is already divided by 100
        obj_valuation_diff_ratio = Eval(float_to_decimal, Dict('contrat/pourcentagePerformanceContrat', default=None))

    def has_investments(self):
        return Dict('contrat/listeSupports', default=None)(self.doc)

    @method
    class iter_cards(DictElement):
        item_xpath = 'contrat/listeCartes'

        class item(ItemElement):
            klass = Account

            def condition(self):
                # Keep only deferred card with available details
                return (
                    Dict('nature')(self) == 'DIFFERE' and
                    isinstance(Dict('montant', default=None)(self), float)
                )

            obj_id = obj_number = Dict('numero')
            obj_label = Format('%s %s', CleanText(Dict('libelle')), CleanText(Dict('numero')))
            obj_currency = Currency(Dict('devise'))
            obj_type = Account.TYPE_CARD
            obj__category = 'Carte'
            obj_balance = Decimal(0)
            obj_coming = CleanDecimal.US(
                Format('%s%s', Dict('signe'), Eval(float_to_decimal, Dict('montant')))
            )
            obj__url = NotAvailable

    @method
    class iter_investments(DictElement):
        item_xpath = 'contrat/listeSupports'

        class item(ItemElement):
            klass = Investment

            obj_label = CleanText(Dict('libelleSupport'))
            obj_valuation = Eval(float_to_decimal, Dict('montantSupport'))
            obj_quantity = Eval(float_to_decimal, Dict('nbUniteCompte', default=None))
            obj_unitvalue = Eval(float_to_decimal, Dict('valeurUniteCompte', default=None))
            obj_portfolio_share = Eval(lambda x: float_to_decimal(x) / 100, Dict('tauxSupport', default=None))
            obj_code = IsinCode(Dict('codeISIN', default=None), default=NotAvailable)
            obj_code_type = IsinType(Dict('codeISIN', default=None))
            obj_asset_category = CleanText(Dict('classeActif/libelle', default=None))
            # Note: recommended_period & srri are not available on this website

            def obj_performance_history(self):
                perfs = {}
                if Dict('detailPerformance/perfSupportUnAn', default=None)(self):
                    perfs[1] = Eval(lambda x: float_to_decimal(x) / 100, Dict('detailPerformance/perfSupportUnAn'))(self)
                if Dict('detailPerformance/perfSupportTroisAns', default=None)(self):
                    perfs[3] = Eval(lambda x: float_to_decimal(x) / 100, Dict('detailPerformance/perfSupportTroisAns'))(self)
                if Dict('detailPerformance/perfSupportCinqAns', default=None)(self):
                    perfs[5] = Eval(lambda x: float_to_decimal(x) / 100, Dict('detailPerformance/perfSupportCinqAns'))(self)
                return perfs


class AccountSuperDetailsPage(LoggedPage, JsonPage):
    @method
    class fill_account(ItemElement):
        def obj_balance(self):
            balance = CleanDecimal.US(Dict('montant', default=None), default=None)(self)
            if balance is None:
                balance = CleanDecimal.US(Dict('montantGarantie', default=None), default=None)(self)
            return balance

        # No currency in the json
        obj_currency = 'EUR'


class HistoryPage(LoggedPage, JsonPage):
    @method
    class iter_wealth_history(DictElement):
        item_xpath = '*/historiques'

        class item(ItemElement):
            klass = Transaction

            obj_label = CleanText(Dict('libelle'))
            # There is only one date for each transaction
            obj_date = obj_rdate = Eval(lambda t: datetime.fromtimestamp(int(t) / 1000), Dict('date'))
            obj_type = Transaction.TYPE_BANK

            def obj_amount(self):
                amount = Eval(float_to_decimal, Dict('montant'))(self)
                if Dict('negatif')(self):
                    return -amount
                return amount


GENDERS = {
    'FEMME': 'Female',
    'HOMME': 'Male',
    NotAvailable: NotAvailable
}


class ProfilePage(LoggedPage, JsonPage):
    @method
    class get_profile(ItemElement):
        klass = Person

        obj_name = Dict('identite')
        obj_firstname = Dict('prenom')
        obj_lastname = Dict('nom')
        obj_family_situation = Dict('statutFamilial')
        obj_gender = Map(Dict('sexe', default=NotAvailable), GENDERS)

        def obj_birth_date(self):
            raw_birthdate = Dict('dateNaissance')(self)
            return date.fromtimestamp(raw_birthdate / 1000)


class PortalPage(LoggedPage, HTMLPage):
    def get_account_history_url(self, account_id):
        return Regexp(
            Attr('//a[contains(text(), "%s")]' % account_id, 'onclick'),
            r"'(.*)'"
        )(self.doc)

    @pagination
    @method
    class iter_history(TableElement):
        item_xpath = '//table[@id="releve_operation"]//tr[td]'
        head_xpath = '//table[@id="releve_operation"]//tr/th'

        col_label = 'Libellé'
        col_date = ['Date opé', "Date d'opé"]
        col_debit = 'Débit'
        col_credit = 'Crédit'

        def next_page(self):
            js_link = Attr('//div[@id="pagination"]/a[@class="suivon"]', 'onclick', default=NotAvailable)
            next_link = Regexp(js_link, r"'(.*)'", default=False)(self)
            if next_link:
                next_number_page = Regexp(js_link, r"', (\d+)\)")(self)
                data = {
                    'numCompte': Env('account_id')(self),
                    'vue': 'ReleveOperations',
                    'tri': 'DateOperation',
                    'sens': 'DESC',
                    'page': next_number_page,
                    'nb_element': '25',
                }
                page = self.page.browser.location(next_link, data=data).page
                return page

        class item(ItemElement):
            klass = Transaction

            def condition(self):
                return len(self.el.xpath('./td')) > 2

            obj_date = Date(CleanText(TableCell('date')), dayfirst=True)
            obj_rdate = Date(
                Regexp(CleanText(TableCell('label', colspan=True)), r'(\d+/\d+/\d+)', default=''),
                dayfirst=True,
                default=NotAvailable
            )
            obj_raw = Transaction.Raw(CleanText(TableCell('label')))

            def obj_amount(self):
                return (
                    CleanDecimal.French(TableCell('credit'), default=0)(self)
                    - CleanDecimal.French(TableCell('debit'), default=0)(self)
                )

    @method
    class iter_card_history(TableElement):
        item_xpath = '//table[@id="releve_operation"]//tr[td]'
        head_xpath = '//table[@id="releve_operation"]//tr/th'

        col_label = 'Libellé'
        col_date = 'Date'
        col_amount = 'Montant'

        class item(ItemElement):
            klass = Transaction

            def condition(self):
                return len(self.el.xpath('./td')) > 2

            obj_label = CleanText(TableCell('label'))
            obj_rdate = Date(CleanText(TableCell('date')), dayfirst=True)
            obj_amount = CleanDecimal.French(TableCell('amount'), sign='-')
            obj_type = Transaction.TYPE_CARD
            obj_date = Date(
                Regexp(
                    CleanText('//div[@class="entete1_bloc"]/p[contains(text(), "Débité le")]'),
                    r'Débité le (.+) :'
                ),
                parse_func=parse_french_date,
            )
