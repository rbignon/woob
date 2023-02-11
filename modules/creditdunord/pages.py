# -*- coding: utf-8 -*-

# Copyright(C) 2012 Romain Bignon
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
from datetime import date
from decimal import Decimal
from io import BytesIO

from dateutil.relativedelta import FR, relativedelta

from woob.browser.pages import HTMLPage, LoggedPage, JsonPage
from woob.browser.elements import method, ItemElement, DictElement
from woob.browser.filters.standard import (
    CleanText, Date, CleanDecimal, Regexp, Format, Field,
    Env, Map, MapIn, Currency,
)
from woob.browser.filters.json import Dict
from woob.capabilities.base import empty
from woob.exceptions import ActionNeeded, BrowserUnavailable
from woob.capabilities.bank import Account, AccountOwnership, Loan
from woob.capabilities.bank.wealth import Investment
from woob.capabilities.profile import Person, Company
from woob.capabilities import NotAvailable
from woob.tools.capabilities.bank.transactions import FrenchTransaction
from woob.tools.capabilities.bank.investments import IsinCode, IsinType
from woob.tools.captcha.virtkeyboard import GridVirtKeyboard


class CDNVirtKeyboard(GridVirtKeyboard):
    symbols = {
        '0': '3de2346a63b658c977fce4da925ded28',
        '1': 'c571018d2dc267cdf72fafeeb9693037',
        '2': '72d7bad4beb833d85047f6912ed42b1d',
        '3': 'fbfce4677a8b2f31f3724143531079e3',
        '4': '54c723c5b0b5848a0475b4784100b9e0',
        '5': 'd00164307cacd4ca21b930db09403baa',
        '6': '101adc6f5d03df0f512c3ec2bef88de9',
        '7': '3b48f598209718397eb1118d81cf07ba',
        '8': '881f0acdaba2c44b6a5e64331f4f53d3',
        '9': 'a47d9a0a2ebbc65a0e625f20cb07822b',
    }

    margin = 1
    color = (0xff, 0xf7, 0xff)
    nrow = 4
    ncol = 4

    def __init__(self, browser, crypto, grid):
        f = BytesIO(browser.open('/sec/vk/gen_ui?modeClavier=0&cryptogramme=%s' % crypto).content)

        super(CDNVirtKeyboard, self).__init__(range(16), self.ncol, self.nrow, f, self.color)
        self.check_symbols(self.symbols, browser.responses_dirname)
        self.codes = grid

    def check_color(self, pixel):
        for p in pixel:
            if p > 0xd0:
                return False
        return True

    def get_string_code(self, string):
        res = []
        ndata = self.nrow * self.ncol
        for nbchar, c in enumerate(string):
            index = self.get_symbol_code(self.symbols[c])
            res.append(self.codes[(nbchar * ndata) + index])
        return ','.join(map(str, res))


class HTMLErrorPage(HTMLPage):
    def get_website_unavailable_message(self):
        return CleanText('//head/title[text()="Site momentanément indisponible"]')(self.doc)

    def get_error(self):
        # No Coalesce here as both can be empty
        return (
            CleanText('//b[has-class("x-attentionErreurLigneHaut")]')(self.doc)
            or CleanText('//div[has-class("x-attentionErreur")]/b')(self.doc)
        )


class RedirectPage(HTMLPage):
    def on_load(self):
        link = Regexp(CleanText('//script'), 'href="(.*)"', default='')(self.doc)
        if link:
            self.browser.location(link)


class IndexPage(HTMLPage):
    def skip_redo_2fa(self):
        form = self.get_form()
        form.submit()


class LoginConfirmPage(JsonPage):
    def get_reason(self):
        return Dict('commun/raison', default='')(self.doc)

    def get_status(self):
        return Dict('commun/statut')(self.doc).upper()

    def is_pro_space(self):
        return 'connexion_pro' in Dict('donnees/url')(self.doc)


class LoginPage(HTMLErrorPage):
    VIRTUALKEYBOARD = CDNVirtKeyboard

    def login(self, username, password):
        res = self.browser.open('/sec/vk/gen_crypto.json').json()
        crypto = res['donnees']['crypto']
        grid = res['donnees']['grid']

        vk = self.VIRTUALKEYBOARD(self.browser, crypto, grid)

        data = {
            'user_id': username,
            'vk_op': 'auth',
            'codsec': vk.get_string_code(password),
            'cryptocvcs': crypto,
        }
        self.browser.location('/sec/vk/authent.json', data=data)

    def classic_login(self, username, password):
        m = re.match(r'https://www.([^\.]+).fr', self.browser.BASEURL)
        if not m:
            bank_name = 'credit-du-nord'
            self.logger.error('Unable to find bank name for %s' % self.browser.BASEURL)
        else:
            bank_name = m.group(1)

        data = {
            'bank': bank_name,
            'pagecible': 'vos-comptes',
            'password': password.encode(self.browser.ENCODING),
            'pwAuth': 'Authentification+mot+de+passe',
            'username': username.encode(self.browser.ENCODING),
        }
        self.browser.location('/saga/authentification', data=data)


class ErrorPage(HTMLPage):
    def get_error_msg(self):
        return CleanText('//h1[contains(text(), "Erreur technique")]/following-sibling::p')(self.doc)


class LoggedDetectionMixin(object):
    @property
    def logged(self):
        return Dict('commun/raison', default=None)(self.doc) != "niv_auth_insuff"


class JsonLoggedBasePage(LoggedDetectionMixin, JsonPage):
    pass


class ProfilePage(JsonLoggedBasePage):
    def on_load(self):
        if CleanText(Dict('commun/statut', default=''))(self.doc).upper() == 'NOK':
            reason = CleanText(Dict('commun/raison', default=None), default='')(self.doc)
            assert reason in REASONS_MAPPING, 'Unhandled error : %s' % reason
            raise ActionNeeded(REASONS_MAPPING[reason])

    def get_profile(self):
        user_type = CleanText(Dict('donnees/marche', default=''))(self.doc).upper()
        if user_type in ('PRO', 'ENT'):
            profile = Company()
        else:
            profile = Person()
            profile.firstname = CleanText(Dict('donnees/nom'))(self.doc)
            profile.lastname = CleanText(Dict('donnees/prenom', default=None), default=NotAvailable)(self.doc)

        profile.name = CleanText(Format(
            '%s %s',
            CleanText(Dict('donnees/nom')),
            CleanText(Dict('donnees/prenom'), default='')
        ))(self.doc)

        profile.email = CleanText(Dict('donnees/email', default=None), default=NotAvailable)(self.doc)

        return profile


class RgpdPage(LoggedPage, HTMLPage):
    pass


class BypassAlertPage(JsonLoggedBasePage):
    pass


REASONS_MAPPING = {
    'SCA': 'Vous devez réaliser la double authentification sur le portail internet',
    'SCAW': 'Vous devez choisir si vous souhaitez dès à présent activer la double authentification sur le portail internet',
    'GDPR': 'GDPR',
    'alerting_pull_incitation': 'Mise à jour de votre dossier',  # happens when the user needs to send a document ID
}


ACCOUNT_TYPES = {
    'COMPTE_COURANT': Account.TYPE_CHECKING,
    'CARTE': Account.TYPE_CARD,
    'PLACEMENT_BANCAIRE': Account.TYPE_SAVINGS,
    'PLACEMENT_FINANCIER': Account.TYPE_MARKET,
    'CREDIT_CONSOMMATION': Account.TYPE_CONSUMER_CREDIT,
    'CREDIT_IMMOBILIER': Account.TYPE_MORTGAGE,
    'CREDIT_AUTRE': Account.TYPE_REVOLVING_CREDIT,
}

ACCOUNT_EXTENDED_TYPES = {
    'ORD': Account.TYPE_MARKET,
    'PEA_PEA_PME': Account.TYPE_PEA,
    'ASSURANCE_VIE': Account.TYPE_LIFE_INSURANCE,
}


class AccountItemElement(ItemElement):
    klass = Account

    def condition(self):
        # multi-bank data, only get this bank's accounts
        return Dict('libelleBanque', default='')(self) == Env('current_bank')(self)

    obj_id = Dict('id')
    obj_label = Dict('intituleCompte')
    obj__custom_id = Dict('customId')

    def obj_type(self):
        type_ = MapIn(CleanText(Dict('bankAccountType')), ACCOUNT_TYPES, Account.TYPE_UNKNOWN)(self)

        extended_type = CleanText(Dict('bankAccountTypeExtended'))(self)
        if extended_type != 'UNKNOWN':
            type_ = Map(
                CleanText(Dict('bankAccountTypeExtended')),
                ACCOUNT_EXTENDED_TYPES,
                type_
            )(self)
        return type_

    def obj_balance(self):
        if Field('type')(self) == Account.TYPE_CARD:
            return Decimal('0.0')
        return CleanDecimal.SI(Dict('montantSolde/valeur'))(self)

    def obj_currency(self):
        # Accounts in EUR have their currency at `null` in the json
        currency = Currency().filter(Dict('montantSolde/devise')(self) or '')
        return currency or 'EUR'

    def obj_coming(self):
        if Field('type')(self) == Account.TYPE_CARD:
            return CleanDecimal.SI(Dict('montantSolde/valeur'))(self)

    def obj__has_investments(self):
        # True for life insurances, PEA and market accounts
        return CleanText(Dict('bankAccountType'))(self) == 'PLACEMENT_FINANCIER'

    def obj_number(self):
        # The first five digits are the bank id
        return CleanText(Dict('identifiantContrat'))(self)[5:]

    def obj_ownership(self):
        account_owner = Regexp(Dict('initialName'), r'[^-]+ - (.*)', default='')(self)  # label can be changed by user
        if not account_owner:
            return NotAvailable

        reg = re.compile(r'(m|mr|me|mme|mlle|mle|ml)\.?\b(.*)\b(m|mr|me|mme|mlle|mle|ml)\b(.*)', re.IGNORECASE)
        if reg.search(account_owner):
            return AccountOwnership.CO_OWNER
        return AccountOwnership.OWNER


class AccountsPage(JsonLoggedBasePage):
    def on_load(self):
        if Dict('commun/statut', default='')(self.doc).upper() == 'NOK':
            reason = Dict('commun/raison')(self.doc)
            assert reason in REASONS_MAPPING, 'Labels page is not available with message %s' % reason
            raise ActionNeeded(REASONS_MAPPING[reason])

    def get_current_bank(self):
        return CleanText(Dict('donnees/libelleBanqueCompteInterne'))(self.doc)

    @method
    class iter_accounts(DictElement):
        item_xpath = 'donnees/compteSyntheseDataFrontList'

        # Some connections have two accounts with the exact same attributes in the json
        ignore_duplicate = True

        class item(AccountItemElement):
            pass

    @method
    class iter_loans(DictElement):
        item_xpath = 'donnees/comptesCreditDataFrontList'

        class item(AccountItemElement):
            klass = Loan

            obj_total_amount = CleanDecimal.SI(Dict('metadatasCred/borrowed'), default=NotAvailable)
            obj_available_amount = CleanDecimal.SI(Dict('metadatasCred/capitalDecaisse'), default=NotAvailable)
            obj_subscription_date = Date(
                CleanText(Dict('metadatasCred/startDate'), default=''), dayfirst=True, default=NotAvailable
            )
            obj_duration = CleanDecimal.SI(Dict('metadatasCred/duration'), default=NotAvailable)

            def obj_rate(self):
                for data in Dict('metadatas/metadata', default=[])(self):
                    if data.get('name') == 'TAUX_AVEC_ASSURANCE':
                        return CleanDecimal.SI(Dict('value'))(data)
                return NotAvailable

            def obj_insurance_rate(self):
                loan_rate = Field('rate')(self)
                if empty(loan_rate):
                    return NotAvailable

                for data in Dict('metadatas/metadata', default=[])(self):
                    if data.get('name') == 'TAUX_HORS_ASSURANCE':
                        rate = CleanDecimal.SI(Dict('value'))(data)
                        return (loan_rate - rate) / 100
                return NotAvailable

            def obj_maturity_date(self):
                if Dict('metadatasCred/endDate')(self) is not None:
                    return Date(CleanText(Dict('metadatasCred/endDate')), dayfirst=True)(self)
                return NotAvailable

            def obj_next_payment_date(self):
                if Dict('metadatasCred/dateMonthlyPayment')(self) is not None:
                    return Date(CleanText(Dict('metadatasCred/dateMonthlyPayment')), dayfirst=True)(self)
                return NotAvailable

            def obj_next_payment_amount(self):
                next_payment_amount = CleanDecimal.SI(Dict('metadatasCred/amountMonthlyPayment'), default=None)(self)
                if next_payment_amount is not None:
                    return next_payment_amount / 100
                return NotAvailable


class IbanPage(JsonLoggedBasePage):
    def get_iban_from_account_number(self, account_number):
        for owner in Dict('donnees/relationBancaires')(self.doc):
            for account in Dict('comptes')(owner):
                if CleanText(Dict('numeroCompte'), replace=[(' ', '')])(account) == account_number:
                    return CleanText(Dict('iban'))(account)

    def get_status(self):
        return Dict('commun/statut')(self.doc).upper()


class Transaction(FrenchTransaction):
    PATTERNS = [
        (
            re.compile(r'^(?P<text>RET DAB \w+ .*?) LE (?P<dd>\d{2})\.?(?P<mm>\d{2})$'),
            FrenchTransaction.TYPE_WITHDRAWAL,
        ),
        (
            re.compile(r'^(E-)?VIR(EMENT)?( INTERNET)?( SEPA)?(\.| )?(DE)? (?P<text>.*?)( Motifs? :.*)?$'),
            FrenchTransaction.TYPE_TRANSFER,
        ),
        (re.compile(r'^FRAIS(/)?(?P<text>.*)'), FrenchTransaction.TYPE_BANK),
        (re.compile(r'^PRLV (SEPA )?(DE )?(?P<text>.*?)( Motifs? :.*)?$'), FrenchTransaction.TYPE_ORDER),
        (re.compile(r'^CB (?P<text>.*) LE (?P<dd>\d{2})\.?(?P<mm>\d{2})$'), FrenchTransaction.TYPE_CARD),
        (re.compile(r'^CARTE (.*?) (?P<text>.*) LE (?P<dd>\d{2})\.?(?P<mm>\d{2})$'), FrenchTransaction.TYPE_CARD),
        (re.compile(r'^CHEQUE.*'), FrenchTransaction.TYPE_CHECK),
        (re.compile(r'^(CONVENTION \d+ )?COTISATION (?P<text>.*)'), FrenchTransaction.TYPE_BANK),
        (re.compile(r'^REM(ISE)?\.?( CHQ\.)? .*'), FrenchTransaction.TYPE_DEPOSIT),
        (re.compile(r'^(?P<text>.*?)( \d{2}.*)? LE (?P<dd>\d{2})\.?(?P<mm>\d{2})$'), FrenchTransaction.TYPE_CARD),
        (re.compile(r'^(?P<text>.*?) LE (?P<dd>\d{2}) (?P<mm>\d{2}) (?P<yy>\d{2})$'), FrenchTransaction.TYPE_CARD),
        (re.compile(r'^(?=.*\bFIN)(?=.*\bPRET\b).*$'), FrenchTransaction.TYPE_LOAN_PAYMENT),
        (re.compile(r'^ACHATS CARTE.*'), FrenchTransaction.TYPE_CARD_SUMMARY),
        (re.compile(r'^TOTAL DES ACHATS DU MOIS.*'), FrenchTransaction.TYPE_CARD_SUMMARY),
    ]


class HistoryPage(JsonLoggedBasePage):
    def has_transactions(self, has_investments):
        return (has_investments and Dict('donnees/listeOpsBPI')(self.doc)) or Dict('donnees/listeOps')(self.doc)

    def check_reason(self):
        if Dict('commun/statut')(self.doc).upper() == 'NOK':
            reason = Dict('commun/raison')(self.doc)
            if reason == 'err_tech':
                raise BrowserUnavailable()
            raise AssertionError('Unhandled not ok reason: %s' % reason)

    @method
    class iter_history(DictElement):
        item_xpath = 'donnees/listeOps'

        class item(ItemElement):
            klass = Transaction

            obj_amount = CleanDecimal.SI(Dict('amount'))
            obj_vdate = Date(CleanText(Dict('dateVal'), default=''), default=NotAvailable, dayfirst=True)
            obj_rdate = Date(CleanText(Dict('dateTransac'), default=''), default=NotAvailable, dayfirst=True)

            def obj_date(self):
                date = Date(CleanText(Dict('dateOp')), dayfirst=True)(self)

                def _set_correct_last_weekday(last_wdate):
                    if last_wdate.weekday() > 4:  # Sat, Sun
                        # in the weekend, so we return the last previous friday
                        last_wdate += relativedelta(weekday=FR(-1))
                    return last_wdate

                if Env('account_type')(self) == Account.TYPE_CARD:
                    # debit dates are not given on the new website yet
                    # but they correspond to the last weekday of the month

                    last_wdate = date + relativedelta(day=31)
                    last_wdate = _set_correct_last_weekday(last_wdate)

                    if date >= last_wdate:
                        # date in the last days of the month, but after the last week day,
                        # so debit date is in the next month
                        # ex: date=2020, 11, 30 -> go to last day of next month (2020, 12, 31)
                        # -> then find the last weekday (ok, it is a friday)
                        last_wdate += relativedelta(months=1) + relativedelta(day=31)
                        last_wdate = _set_correct_last_weekday(last_wdate)

                    date = last_wdate

                return date

            def obj_raw(self):
                # date is parsed in a 'def obj_*' method, and those are run after 'obj_*' ones.
                # raw parsing is not used for date, so, for it to do the rest of parsing,
                # it must also be a 'def obj_*', and done after date
                return Transaction.Raw(CleanText(Dict('label')))(self)

            def obj_type(self):
                if (
                    Env('account_type')(self) == Account.TYPE_CARD
                    and self.obj.type == Transaction.TYPE_CARD
                ):
                    return Transaction.TYPE_DEFERRED_CARD

                return self.obj.type

            def obj__is_coming(self):
                return Field('date')(self) > date.today()

    @method
    class iter_wealth_history(DictElement):
        item_xpath = 'donnees/listeOpsBPI'

        class item(ItemElement):
            klass = FrenchTransaction

            obj_label = CleanText(Dict('label'))
            obj_amount = CleanDecimal.SI(Dict('amount'))
            obj_date = Date(CleanText(Dict('dateOp')), dayfirst=True)
            obj_type = FrenchTransaction.TYPE_BANK

            def obj__is_coming(self):
                return Field('date')(self) > date.today()


class InvestmentsPage(JsonLoggedBasePage):
    def has_investments(self):
        return Dict('donnees/assetDataFront/entries')(self.doc) is not None

    @method
    class iter_investment(DictElement):
        item_xpath = 'donnees/assetDataFront/entries'

        class item(ItemElement):
            klass = Investment

            def condition(self):
                return Field('valuation')(self) != 0

            obj_label = CleanText(Dict('label'))
            obj_valuation = CleanDecimal.SI(Dict('amount'))
            obj_vdate = Date(CleanText(Dict('valueDate'), default=''), default=NotAvailable, dayfirst=True)
            obj_quantity = CleanDecimal.SI(Dict('quantity'), default=NotAvailable)
            obj_unitprice = CleanDecimal.SI(Dict('costPrice'), default=NotAvailable)
            obj_unitvalue = CleanDecimal.SI(Dict('sharePrice'), default=NotAvailable)
            obj_code = IsinCode(CleanText(Dict('isin')), default=NotAvailable)
            obj_code_type = IsinType(CleanText(Dict('isin')))

            def obj_portfolio_share(self):
                portfolio_share = CleanDecimal.SI(Dict('percentages'), default=NotAvailable)(self)
                if portfolio_share:
                    return portfolio_share / 100
