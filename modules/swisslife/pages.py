# -*- coding: utf-8 -*-

# Copyright(C) 2012-2021  Budget Insight
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

import datetime

from weboob.browser.elements import method, ListElement, ItemElement, DictElement
from weboob.browser.filters.json import Dict
from weboob.browser.filters.standard import (
    CleanText, CleanDecimal, Eval, Field, Map, Currency, Regexp,
    Env, Date, BrowserURL, Coalesce, MultiJoin, MapIn, Lower,
)
from weboob.browser.pages import LoggedPage, JsonPage, HTMLPage
from weboob.capabilities.bank import Account, Transaction
from weboob.capabilities.wealth import Investment
from weboob.capabilities.profile import Person
from weboob.capabilities.base import NotAvailable, empty
from weboob.tools.compat import urlparse
from weboob.tools.capabilities.bank.transactions import FrenchTransaction
from weboob.tools.capabilities.bank.investments import IsinCode, IsinType
from weboob.tools.date import parse_french_date


def date_from_timestamp(date):
    # 'date' may be None or NotAvailable
    if empty(date):
        return NotAvailable
    return datetime.datetime.fromtimestamp(date/1000)


class MaintenancePage(HTMLPage):
    def is_here(self):
        return bool(CleanText('//h1[contains(text(), "Opération technique exceptionnelle")]')(self.doc))

    def get_error_message(self):
        return CleanText('//h1')(self.doc)


class ProfilePage(LoggedPage, JsonPage):
    @method
    class get_profile(ItemElement):
        klass = Person

        obj_name = MultiJoin(Dict('prenom'), Dict('nom'), pattern=' ')
        obj_email = Dict('emailPrive')
        obj_job = Dict('professionLibelle', default=NotAvailable)
        obj_address = CleanText(MultiJoin(
            Dict('adresse/mentionSupplementaire', default=''),
            Dict('adresse/voie', default=''),
            Dict('adresse/codePostal', default=''),
            Dict('adresse/ville', default=''),
            pattern=' '
        ))


class AccountsPage(LoggedPage, JsonPage):
    def has_accounts(self):
        return Dict('epargne/contrats', default=None)(self.doc) is not None

    @method
    class iter_bank_accounts(DictElement):
        item_xpath = 'epargne/contrats'

        class item(ItemElement):
            klass = Account

            def condition(self):
                return Dict('estBanque')(self)

            ACCOUNT_TYPES = {
                'Espèces': Account.TYPE_DEPOSIT,
                'Titres': Account.TYPE_MARKET,
                'PEA': Account.TYPE_PEA,
            }

            obj_id = obj_number = CleanText(Dict('compteNumero'))
            obj_label = CleanText(Dict('compteLibelle'))

            def obj_type(self):
                account_type = MapIn(CleanText(Dict('compteType')), self.ACCOUNT_TYPES, Account.TYPE_UNKNOWN)(self)
                if account_type == Account.TYPE_UNKNOWN:
                    self.logger.warning('Could not type account "%s"', Field('label')(self))
                return account_type

            def obj_opening_date(self):
                return parse_french_date(Dict('ouvertureDate')(self))

            obj_balance = CleanDecimal.SI(Dict('soldeDeviseCompteMontant'))
            obj_currency = Currency(Dict('devise'))

            obj__profile_types = NotAvailable
            obj__fiscality_type = NotAvailable
            obj__history_urls = NotAvailable

            obj__is_bank_account = True

            obj_url = BrowserURL('bank_account_detail', id=Field('id'))

    @method
    class iter_wealth_accounts(DictElement):
        item_xpath = 'epargne/contrats'

        class item(ItemElement):
            klass = Account

            def condition(self):
                if Dict('estBanque')(self) or Dict('estResilie')(self):
                    return False
                # Only these accounts have a details URL and a balance.
                return any((
                    Dict('estVieArt39IFC')(self),
                    Dict('estVieUC')(self),
                    Dict('estContratBull')(self),
                    Dict('estVieEuro')(self),
                ))

            ACCOUNT_TYPES = {
                'EPARGNE RETRAITE': Account.TYPE_PERP,
                'ARTICLE 83': Account.TYPE_ARTICLE_83,
                'SWISSLIFE RETRAITE ENTREPRISES': Account.TYPE_ARTICLE_83,
                'SWISSLIFE RETRAITE ARTICLE 83': Account.TYPE_ARTICLE_83,
                'SWISSLIFE PER ENTREPRISES': Account.TYPE_PER,
                'SWISS RETRAITE ADDITIVE': Account.TYPE_ARTICLE_83,
                'GARANTIE RETRAITE': Account.TYPE_LIFE_INSURANCE,
                'GARANTIE RETRAITE ENTREPRISES 2000': Account.TYPE_LIFE_INSURANCE,
                'GARANTIE RETRAITE INDEPENDANTS 2000': Account.TYPE_LIFE_INSURANCE,
                'RETRAITE ART 83 CGI MULTISUPPORTS': Account.TYPE_ARTICLE_83,
                'ERES RETRAITE 83 V2': Account.TYPE_ARTICLE_83,
                'SWISSLIFE INDEM FIN DE CARRIERES': Account.TYPE_PER,
                'SWISSLIFE PER INDIVIDUEL': Account.TYPE_PER,
            }

            obj_id = obj_number = CleanText(Dict('numContrat'))
            obj__contract_id = CleanText(Dict('contratId'))
            obj_label = CleanText(Dict('libelleProduit'))

            obj_currency = 'EUR'

            obj__is_bank_account = False
            obj__is_market_account = True

            def obj_opening_date(self):
                return date_from_timestamp(Dict('dateEffet')(self))

            def obj_type(self):
                account_type = Map(Field('label'), self.ACCOUNT_TYPES, Account.TYPE_UNKNOWN)(self)
                return account_type

            def obj_url(self):
                # Article 39 accounts have a specific JSON that only contains the balance
                if Dict('estVieArt39IFC')(self):
                    return self.page.browser.absurl('/api/v3/contratVieucEntreprise/encours/%s' % Field('id')(self))
                # Regular accounts
                elif Dict('estVieUC')(self) and not Dict('estResilie')(self):
                    if Dict('typeContrat')(self) == 'ADHERENT':
                        return BrowserURL('account_vie_ucco', id=Field('id'))(self)
                    return BrowserURL('account_detail', id=Field('id'))(self)
                # Life insurances and retirement plans
                elif Dict('estVieEuro')(self) and not Dict('estResilie')(self):
                    if Dict('estEpargne')(self):
                        return BrowserURL('account_vie_euro', id=Field('_contract_id'))(self)
                    return BrowserURL('account_vie_euro', id=Field('_contract_id'))(self)
                # TODO: The following assert is replaced temporarily by a warning.
                #  It should be reverted after the release when we find the correct url for these accounts.
                # assert False, 'Could not find details URL for account %s' % Field('id')(self)
                self.logger.warning('Could not find details URL for account %s', Field('id')(self))


class IterInvestment(ListElement):
    class item(ItemElement):
        klass = Investment

        obj_label = Dict('nomSupport')
        obj_quantity = CleanDecimal.SI(Dict('nbPart', default=''), default=NotAvailable)
        obj_unitvalue = CleanDecimal.SI(Dict('valPart',  default=''), default=NotAvailable)
        obj_valuation = CleanDecimal.SI(Dict('montantNet'))
        obj_diff = CleanDecimal.SI(Dict('evolution', default=''), default=NotAvailable)
        obj__nature = Dict('codeNature')
        obj_code = IsinCode(CleanText(Dict('codeIsin')), default=NotAvailable)
        obj_code_type = IsinType(CleanText(Dict('codeIsin')), default=NotAvailable)

        def obj_unitprice(self):
            unitprice = CleanDecimal.SI(Dict('prixMoyenAchat', default=''), default=NotAvailable)(self)
            if unitprice == 0:
                return NotAvailable
            return unitprice

        def obj_vdate(self):
            return date_from_timestamp(Dict('dateValeur', default=NotAvailable)(self))

    def find_elements(self):
        for el in self.el:
            yield el


class BankAccountDetailPage(LoggedPage, JsonPage):
    def is_market_account(self):
        return Dict('operationsListe/estTitre')(self.doc)

    @method
    class iter_investment(DictElement):
        def find_elements(self):
            # All investments are not on the same depth.
            # Investments with stocks are grouped in a single investment so we must skip it and get them instead.
            for obj in Dict('positions/data')(self):
                if Dict('actions', default=None)(obj) is None:
                    yield obj
                else:
                    for sub_obj in Dict('actions')(obj):
                        yield sub_obj

        class item(ItemElement):
            klass = Investment

            # Investment characteristics are stored in a field data (when it exists) that looks like this:
            # "data": [
            #   {"key": "XXX", "value": "XXX"},
            #   {"key": "XXX", "value": "XXX"},
            #   ...
            # ]
            def parse(self, el):
                for obj in Dict('caracteristiques/data', default={})(el):
                    key = CleanText(Dict('key', default=NotAvailable), default=NotAvailable)(obj)
                    value = Dict('value', default=NotAvailable)(obj)

                    if empty(key) or empty(value):
                        continue

                    if key == 'Code ISIN':
                        self.env['code'] = IsinCode(default=NotAvailable).filter(
                            CleanText(default=NotAvailable).filter(value)
                        )
                        self.env['code_type'] = IsinType(default=NotAvailable).filter(
                            CleanText(default=NotAvailable).filter(value)
                        )
                    elif key == '+/- value latente':
                        self.env['diff'] = CleanDecimal.French(default=NotAvailable).filter(value)
                    elif key == 'Quantité':
                        self.env['quantity'] = CleanDecimal.SI(default=NotAvailable).filter(value)
                    elif key == 'Prix de revient unitaire':
                        self.env['unitprice'] = CleanDecimal.French(default=NotAvailable).filter(value)
                    elif key == 'Valorisation du titre':
                        self.env['unitvalue'] = CleanDecimal.French(default=NotAvailable).filter(value)
                    elif key == 'Date de valorisation':
                        self.env['vdate'] = Date(default=NotAvailable, parse_func=parse_french_date).filter(
                            CleanText(default=NotAvailable).filter(value)
                        )

            obj_valuation = CleanDecimal.French(Dict('montant'))
            obj_code = Env('code', default=NotAvailable)
            obj_code_type = Env('code_type', default=NotAvailable)
            obj_diff = Env('diff', default=NotAvailable)
            obj_quantity = Env('quantity', default=NotAvailable)
            obj_unitprice = Env('unitprice', default=NotAvailable)
            obj_unitvalue = Env('unitvalue', default=NotAvailable)
            obj_vdate = Env('vdate', default=NotAvailable)
            obj_label = Coalesce(
                Regexp(CleanText(Dict('libelle')), r'(.*) \(', default=None),
                CleanText(Dict('libelle'))
            )

            def obj_portfolio_share(self):
                percentage = CleanDecimal.SI(Dict('pourcentage'))(self)
                if percentage:
                    return percentage / 100
                return NotAvailable


class BankAccountTransactionsPage(LoggedPage, JsonPage):
    def has_operations(self):
        return Dict('operations', default=None)(self.doc) is not None

    def has_next_page(self, size):
        return self.has_operations() and len(Dict('operations', default={})(self.doc)) == size

    @method
    class iter_history(DictElement):
        item_xpath = 'operations'

        class item(ItemElement):
            klass = Transaction

            # Transaction characteristics are stored in a field detailData that looks like this:
            # "data": [
            #   {"key": "XXX", "value": "XXX"},
            #   {"key": "XXX", "value": "XXX"},
            #   ...
            # ]
            def parse(self, el):
                for obj in Dict('detailData')(el):
                    key = CleanText(Dict('key', default=NotAvailable), default=NotAvailable)(obj)
                    value = Dict('value', default=NotAvailable)(obj)

                    if empty(key) or empty(value):
                        continue

                    if key == "Date de valeur de l'opération" or key == "Date de valeur":
                        self.env['vdate'] = Date(default=NotAvailable, parse_func=parse_french_date).filter(
                            CleanText(default=NotAvailable).filter(value)
                        )
                    elif key == "Date d'exécution":
                        self.env['rdate'] = Date(default=NotAvailable, parse_func=parse_french_date).filter(
                            Regexp(pattern=r'(.*) \d+h\d+', default=NotAvailable).filter(
                                CleanText(default=NotAvailable).filter(value)
                            )
                        )
                    elif key == 'Quantité':
                        self.env['quantity'] = CleanDecimal.SI(default=NotAvailable).filter(value)
                    elif key == "Prix unitaire moyen":
                        self.env['unitprice'] = CleanDecimal.French(default=NotAvailable).filter(value)

            # TODO This list of labels is from the API test environment, it should be revised.
            TRANSACTION_TYPES = {
                'frais de tenue': Transaction.TYPE_BANK,
                "frais d'administration": Transaction.TYPE_BANK,
                'envoi chequier': Transaction.TYPE_BANK,
                'operation': Transaction.TYPE_BANK,
                'saisie de valeurs': Transaction.TYPE_BANK,
                'blocage de fonds': Transaction.TYPE_BANK,
                'droits de garde': Transaction.TYPE_BANK,
                'dividende': Transaction.TYPE_BANK,
                'conversion': Transaction.TYPE_BANK,
                'interets': Transaction.TYPE_BANK,
                'apport': Transaction.TYPE_TRANSFER,
                'versement': Transaction.TYPE_TRANSFER,
                'virement': Transaction.TYPE_TRANSFER,
                'cheque': Transaction.TYPE_CHECK,
                'paiement en faveur': Transaction.TYPE_ORDER,
            }

            obj_amount = CleanDecimal.French(Dict('deviseMontant'))
            obj_label = CleanText(Dict('operationLibelle'))
            obj_date = Date(CleanText(Dict('operationDate')), parse_func=parse_french_date)
            obj_vdate = Env('vdate', default=NotAvailable)
            obj_rdate = Env('rdate', default=NotAvailable)

            def obj_type(self):
                if Dict('instrumentFinancier', default=None)(self):
                    return Transaction.TYPE_BANK
                account_type = MapIn(Lower(Field('label'), transliterate=True), self.TRANSACTION_TYPES, default=Transaction.TYPE_UNKNOWN)(self)
                if account_type == Transaction.TYPE_UNKNOWN:
                    self.logger.warning('Could not type transaction "%s"', Field('label')(self))
                return account_type

            def obj_investments(self):
                if Dict('instrumentFinancier', default=None)(self) is None:
                    return NotAvailable
                inv = Investment()
                inv.valuation = Eval(lambda x: abs(x), Field('amount'))(self)
                inv.label = Regexp(CleanText(Dict('instrumentFinancier')), r'(.*) \(', default=None)(self) \
                            or CleanText(Dict('instrumentFinancier'))(self)
                inv.code = IsinCode(Regexp(CleanText(Dict('instrumentFinancier')), r'.* \((.*)\)', default=''), default=NotAvailable)(self)
                inv.code_type = IsinType(Regexp(CleanText(Dict('instrumentFinancier')), r'.* \((.*)\)', default=''), default=NotAvailable)(self)
                inv.quantity = Env('quantity')(self)
                inv.unitprice = Env('unitprice')(self)
                return [inv]


class AccountDetailPage(LoggedPage, JsonPage):
    def is_error(self):
        # OK status can be null or 200
        return CleanText(Dict('status', default=''))(self.doc) not in ('', '200')

    TYPES = {
        'MADELIN': Account.TYPE_MADELIN,
        'Article 83': Account.TYPE_ARTICLE_83,
        'PERP': Account.TYPE_PERP,
    }

    @method
    class fill_account(ItemElement):
        obj_currency = 'EUR'
        obj_balance = CleanDecimal(Dict('encours/montantNetDeFrais', default='0'))
        obj_valuation_diff = CleanDecimal(Dict('encours/plusValue', default=''), default=NotAvailable)
        obj__history_urls = NotAvailable

        def obj__profile_types(self):
            profile_types = []
            for v in Dict('profils', default=NotAvailable)(self).values():
                if isinstance(v, dict) and "typeProfil" in v:
                    profile_types.append(v['typeProfil'])
            return profile_types

        def obj__fiscality_type(self):
            return Map(Dict('fiscalite', default=''), self.page.TYPES, Account.TYPE_LIFE_INSURANCE)(self)

    @method
    class iter_history(ListElement):
        class item(ItemElement):
            klass = FrenchTransaction

            obj_raw = FrenchTransaction.Raw(Dict('nature'))
            obj_amount = CleanDecimal(Dict('montantBrut'))

            def obj_date(self):
                return date_from_timestamp(Dict('dateEffet', default=NotAvailable)(self))

            def obj_investments(self):
                l = Dict('supports')(self)
                m = IterInvestment(self.page, el=l)
                return list(m())

        def find_elements(self):
            if 'mouvements' in self.el:
                for el in self.el.get('mouvements', ()):
                    yield el


class AccountVieEuroPage(AccountDetailPage):
    @method
    class fill_account(ItemElement):
        obj_balance = Dict('rachatValeurMontant') & CleanDecimal
        obj_valuation_diff = CleanDecimal(Dict('plusValueMontant', default=''), default=NotAvailable)
        obj__profile_types = NotAvailable
        obj__history_urls = NotAvailable
        obj__fiscality_type = NotAvailable

    @method
    class iter_history(ListElement):
        class item(ItemElement):
            klass = FrenchTransaction

            obj_raw = Eval(lambda t: 'Primes' if t == 'PRI' else 'Règlement', Dict('operation/natureCode'))
            obj_amount = Eval(lambda t: t/100, CleanDecimal.SI(Dict('montantBrut', default='0')))

            def obj_date(self):
                return date_from_timestamp(Dict('effetDate', default=NotAvailable)(self))

            # "impaye" returns timestamp -2211757200000 which raises an error in backend
            def validate(self, obj):
                return obj.date.year > 1969

        def find_elements(self):
            for el in self.el:
                yield el


class AccountVieUCCOPage(AccountDetailPage):
    @method
    class fill_account(ItemElement):
        obj_balance = CleanDecimal.SI(Dict('encours/montantEpargne', default='0'))
        # Currency not available in the JSON. hardcoded until someone get a life-insurance != EUR
        obj_currency = "EUR"
        obj__profile_types = NotAvailable
        obj__fiscality_type = NotAvailable

        def obj__history_urls(self):
            parsed_url = urlparse(self.obj.url)
            history_url = 'https://' + parsed_url.netloc + parsed_url.path + '/operations?' + parsed_url.query
            return [history_url]

    @method
    class iter_investment(IterInvestment):
        def find_elements(self):
            for el in self.el.get('encoursListe', ()):
                yield el


class AccountVieUCPage(AccountDetailPage):
    @method
    class fill_account(ItemElement):
        obj_balance = CleanDecimal.SI(Dict('rachatValeurMontant', default='0'))
        obj__history_urls = NotAvailable
        obj__profile_types = NotAvailable
        obj__fiscality_type = NotAvailable

    @method
    class iter_investment(DictElement):

        class item(ItemElement):
            klass = Investment

            obj_label = CleanText(Dict('nomSupport'))
            obj_valuation = CleanDecimal.SI(Dict('montantNet'))
            obj_quantity = CleanDecimal.SI(Dict('nbPart'))
            obj_unitvalue = CleanDecimal.SI(Dict('valPart'))
            obj_code = IsinCode(Dict('codeIsin'), default=NotAvailable)
            obj_code_type = IsinType(Dict('codeIsin'), default=NotAvailable)

            def obj_unitprice(self):
                unitprice = CleanDecimal.SI(Dict('prixMoyenAchat'))(self)
                if unitprice == 0:
                    return NotAvailable
                return unitprice

            def obj_vdate(self):
                return date_from_timestamp(Dict('dateValeur', default=NotAvailable)(self))

    @method
    class iter_history(DictElement):
        item_xpath = 'operationItems'

        class item(ItemElement):
            klass = FrenchTransaction

            obj_id = Dict('operationId')
            obj_label = CleanText(Dict('natureLibelle'))
            obj_amount = CleanDecimal.SI(Dict('montantBrut'))
            obj_type = FrenchTransaction.TYPE_BANK

            def obj_date(self):
                return date_from_timestamp(Dict('effetDate', default=NotAvailable)(self))

            def obj_vdate(self):
                return date_from_timestamp(Dict('effetDate', default=NotAvailable)(self))

            def validate(self, obj):
                return CleanText(Dict('etatLibelle'))(self) == 'Validé'


class AccountVieUCCODetailPage(LoggedPage, JsonPage):
    @method
    class iter_history(ListElement):
        class item(ItemElement):
            klass = FrenchTransaction

            obj_raw = FrenchTransaction.Raw(Dict('nature'))
            obj_amount = CleanDecimal.SI(Dict('montantBrut'))
            obj__fiscality_type = NotAvailable

            def obj_date(self):
                return date_from_timestamp(Dict('dateEffet', default=NotAvailable)(self))

        def find_elements(self):
            for el in self.el:
                yield el


class InvestmentPage(LoggedPage, JsonPage):
    @method
    class iter_investment(IterInvestment):
        pass
