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

import re
import hashlib
import datetime
from decimal import Decimal
from functools import wraps
from urllib.parse import urljoin, urlencode, urlparse, parse_qs

from woob.browser.pages import (
    HTMLPage, LoggedPage, pagination, NextPage, FormNotFound, PartialHTMLPage,
    LoginPage, CsvPage, RawPage, JsonPage,
)
from woob.browser.elements import (
    ListElement, ItemElement, method, TableElement, SkipItem, DictElement,
)
from woob.browser.filters.standard import (
    CleanText, CleanDecimal, Field, Format,
    Regexp, Date, Eval, Env,
    Currency as CleanCurrency, Map, Coalesce,
    MapIn, Lower, Base, Upper,
)
from woob.browser.filters.json import Dict
from woob.browser.filters.html import Attr, HasElement, Link, TableCell
from woob.capabilities.bank import (
    Account as BaseAccount, Recipient, Transfer, TransferDateType, AccountNotFound,
    AddRecipientBankError, TransferInvalidAmount, Loan, AccountOwnership,
    Emitter, TransferBankError,
)
from woob.capabilities.bank.wealth import (
    Investment, MarketOrder, MarketOrderType, MarketOrderDirection, MarketOrderPayment,
)
from woob.capabilities.base import NotAvailable, Currency, empty
from woob.capabilities.profile import Person
from woob.exceptions import ScrapingBlocked
from woob.tools.capabilities.bank.iban import clean as clean_iban, is_iban_valid
from woob.tools.capabilities.bank.investments import IsinCode, IsinType, create_french_liquidity
from woob.tools.capabilities.bank.transactions import FrenchTransaction
from woob.tools.date import parse_french_date
from woob.tools.json import json
from woob.exceptions import (
    BrowserHTTPNotFound, BrowserUnavailable, ActionNeeded,
)

# Country codes for creating beneficiaries, per alpha-2 code at start of IBAN.
# Actually probably just are Alpha-3 codes, but could be exceptions.
# TODO: Either add a better option or add to the mapping as necessary.
BENEFICIARY_COUNTRY_CODES = {
    'FR': 'FRA',
    'GB': 'GBR',
    'ES': 'ESP',
    'PT': 'PRT',
    'BE': 'BEL',
    'IT': 'ITA',
    'DE': 'DEU',
    'LT': 'LTU',
}


def float_to_int(f):
    if empty(f):
        return NotAvailable
    return int(f)


class IncidentPage(HTMLPage):
    pass


class Account(BaseAccount):
    @property
    def _bourso_type(self):
        return re.search(r'/compte/([^/]+)/', self.url)[1]

    @property
    def _bourso_id(self):
        m = re.search(r'/compte/[^/]+/([a-f0-9]{32})/', self.url)
        if m:
            return m[1]


class IbanPage(LoggedPage, HTMLPage):
    def get_iban(self):
        if (
            self.doc.xpath('//div[has-class("alert")]/p[contains(text(), "Une erreur est survenue")]')
            or self.doc.xpath('//div[has-class("alert")]/p[contains(text(), "Le compte est introuvable")]')
        ):
            return NotAvailable
        return CleanText(
            '//div[strong[contains(text(),"IBAN")]]/div[contains(@class, "definition")]', replace=[(' ', '')]
        )(self.doc)


class AuthenticationPage(HTMLPage):
    def get_confirmation_link(self):
        return Link('//a[contains(@href, "validation")]', default=None)(self.doc)

    def has_skippable_2fa(self):
        return self.doc.xpath(
            '//form[@name="form"]/div[contains(@data-strong-authentication-payload, "Ignorer")]'
        )

    def get_api_config(self):
        json_config = Regexp(
            CleanText('//script[contains(text(), "json config")]'),
            r'CONFIG = (.*}); /'
        )(self.doc)

        return json.loads(json_config)

    def get_otp_number(self):
        return Regexp(
            Attr('//form[@name="form"]/div[@data-strong-authentication-payload]', 'data-strong-authentication-payload'),
            r'resourceId":"(\d+)'
        )(self.doc)


class OtpPage(JsonPage):
    def is_here(self):
        # Same url Than AddRecipientOtpSendPage
        return 'Accès à votre compte' in self.doc.get('msgMask')


class Transaction(FrenchTransaction):
    PATTERNS = [
        (re.compile(r'^(Virement .* )?VIR( SEPA)? (?P<text>.*)'), FrenchTransaction.TYPE_TRANSFER),
        (re.compile(r'^CHQ\. (?P<text>.*)'), FrenchTransaction.TYPE_CHECK),
        (
            re.compile(r'^(ACHAT|PAIEMENT) CARTE (?P<dd>\d{2})(?P<mm>\d{2})(?P<yy>\d{2}) (?P<text>.*)'),
            FrenchTransaction.TYPE_CARD,
        ),
        (
            re.compile(r'^(ACHAT |PAIEMENT )?CARTE (?P<dd>\d{2})/(?P<mm>\d{2})/(?P<yy>\d{2}) (?P<text>.*)'),
            FrenchTransaction.TYPE_CARD,
        ),
        (
            re.compile(r'^(?P<text>.+)?(ACHAT|PAIEMENT) CARTE (?P<dd>\d{2})(?P<mm>\d{2})(?P<yy>\d{4}) (?P<text2>.*)'),
            FrenchTransaction.TYPE_CARD,
        ),
        (
            re.compile(r'^(?P<text>.+)?(ACHAT|PAIEMENT) CARTE (?P<dd>\d{2})/(?P<mm>\d{2})/(?P<yy>\d{4}) (?P<text2>.*)'),
            FrenchTransaction.TYPE_CARD,
        ),
        (
            re.compile(r'^(?P<text>.+)?((ACHAT|PAIEMENT)\s)?CARTE (?P<dd>\d{2})(?P<mm>\d{2})(?P<yy>\d{4}) (?P<text2>.*)'),
            FrenchTransaction.TYPE_CARD,
        ),
        (
            re.compile(r'^(?P<text>.+)?((ACHAT|PAIEMENT)\s)?CARTE (?P<dd>\d{2})/(?P<mm>\d{2})/(?P<yy>\d{4}) (?P<text2>.*)'),
            FrenchTransaction.TYPE_CARD,
        ),
        (
            re.compile(r'(?P<text>.+) CARTE (?P<dd>\d{2})/(?P<mm>\d{2})/(?P<yy>\d{2}) (?P<text2>.*)'),
            FrenchTransaction.TYPE_CARD,
        ),
        (re.compile(r'^(PRLV SEPA |PRLV |TIP )(?P<text>.*)'), FrenchTransaction.TYPE_ORDER),
        (
            re.compile(r'^RETRAIT DAB (?P<dd>\d{2})/?(?P<mm>\d{2})/?(?P<yy>\d{2}) (?P<text>.*)'),
            FrenchTransaction.TYPE_WITHDRAWAL,
        ),
        (
            re.compile(r'^([A-Z][\sa-z]* )?RETRAIT DAB (?P<dd>\d{2})(?P<mm>\d{2})(?P<yy>\d{4}) (?P<text>.*)'),
            FrenchTransaction.TYPE_WITHDRAWAL,
        ),
        (
            re.compile(r'^([A-Z][\sa-z]* )?Retrait dab (?P<dd>\d{2})(?P<mm>\d{2})(?P<yy>\d{4}) (?P<text>.*)'),
            FrenchTransaction.TYPE_WITHDRAWAL,
        ),
        (
            re.compile(r'^AVOIR (?P<dd>\d{2})/?(?P<mm>\d{2})/?(?P<yy>\d{2}) (?P<text>.*)'),
            FrenchTransaction.TYPE_PAYBACK,
        ),
        (
            re.compile(r'^(?P<text>[A-Z][\sa-z]* )?AVOIR (?P<dd>\d{2})(?P<mm>\d{2})(?P<yy>\d{4}) (?P<text2>.*)'),
            FrenchTransaction.TYPE_PAYBACK,
        ),
        (re.compile('^REM CHQ (?P<text>.*)'), FrenchTransaction.TYPE_DEPOSIT),
        (
            re.compile('^([*]{3} solde des operations cb [*]{3} )?Relevé différé Carte (.*)'),
            FrenchTransaction.TYPE_CARD_SUMMARY,
        ),
        (re.compile('^[*]{3} solde des operations cb [*]{3}(.*)'), FrenchTransaction.TYPE_CARD),
        (re.compile(r'^Ech pret'), FrenchTransaction.TYPE_LOAN_PAYMENT),
        (
            re.compile(r'\*INTER(ETS DEBITEURS AU|\.BRUTS) (?P<dd>\d{2})/(?P<mm>\d{2})/(?P<yy>\d{2})'),
            FrenchTransaction.TYPE_BANK,
        ),
        (re.compile(r'^\*.*'), FrenchTransaction.TYPE_BANK),
    ]


class VirtKeyboardPage(HTMLPage):
    pass


class BoursoramaVirtKeyboard(object):
    # sha256 hexdigest of data in src of img
    symbols = {
        '0': '8560081e18568aba02ef3b1f7ac0e8b238cbbd21b70a5e919360ac456d45d506',
        '1': 'eadac6d6288cbd61524fd1a3078a19bf555735c7af13a2890e307263c4c7259b',
        '2': 'c54018639480788c02708b2d89651627dadf74048e029844f92006e19eadc094',
        '3': 'f3022aeced3b8f45f69c1ec001909636984c81b7e5fcdc2bc481668b1e84ae05',
        '4': '3e3d48446781f9f337858e56d01dd9a66c6be697ba34d8f63f48e694f755a480',
        '5': '4b16fb3592febdd9fb794dc52e4d49f5713e9af05486388f3ca259226dcd5cce',
        '6': '9b3afcc0ceb68c70cc697330d8a609900cf330b6aef1fb102f7a1c34cd8bc3d4',
        '7': '9e760193de1b6c5135ebe1bcad7ff65a2aacfc318973ce29ecb23ed2f86d6012',
        '8': '64d87d9a7023788e21591679c1783390011575a189ea82bb36776a096c7ca02c',
        '9': '1b358233ad4eb6b10bf0dadc3404261317a1b78b62f8501b70c646d654ae88f1',
    }

    def __init__(self, page, codesep='|'):
        self.codesep = codesep
        self.fingerprints = {}

        for button in page.doc.xpath('//ul[@class="password-input"]//button'):
            # src is like data:image/svg+xml;base64, [data]
            # so we split to only keep the data
            # hashed so that the symbols dict is smaller
            img_data_hash = hashlib.sha256(
                button.xpath('.//img')[0].attrib['src'].split()[1].encode('utf-8')
            ).hexdigest()
            self.fingerprints[img_data_hash] = button.attrib['data-matrix-key']

    def get_string_code(self, string):
        return self.codesep.join(
            self.fingerprints[self.symbols[digit]] for digit in string
        )


class PasswordPage(LoginPage, HTMLPage):
    TO_DIGIT = {
        'a': '2', 'b': '2', 'c': '2',
        'd': '3', 'e': '3', 'f': '3',
        'g': '4', 'h': '4', 'i': '4',
        'j': '5', 'k': '5', 'l': '5',
        'm': '6', 'n': '6', 'o': '6',
        'p': '7', 'q': '7', 'r': '7', 's': '7',
        't': '8', 'u': '8', 'v': '8',
        'w': '9', 'x': '9', 'y': '9', 'z': '9',
    }

    def enter_password(self, username, password):
        if not password.isdigit():
            old_password = password
            password = ''
            for c in old_password.lower():
                if c.isdigit():
                    password += c
                else:
                    password += self.TO_DIGIT[c]

        keyboard_page = self.browser.keyboard.open()
        vk = BoursoramaVirtKeyboard(keyboard_page)

        form = self.get_form()
        form['form[clientNumber]'] = username
        form['form[password]'] = vk.get_string_code(password)
        form['form[matrixRandomChallenge]'] = Regexp(CleanText('//script'), r'val\("(.*)"')(keyboard_page.doc)
        form.submit()

    def get_error(self):
        return CleanText('//h2[contains(text(), "Erreur")]/following-sibling::div[contains(@class, "msg")]')(self.doc)

    def is_html_loaded(self):
        return HasElement('//title')(self.doc)

    def get_document_cookie(self):
        # Cookie looks like "__brs_mit=842368080c4d0d4b4ed804491e8f7120"
        cookie_name = Regexp(CleanText('//script'), r'document.cookie="(.*?)=', default=None)(self.doc)
        cookie_value = Regexp(CleanText('//script'), fr'="{cookie_name}=(.*?);', default=None)(self.doc)
        return cookie_name, cookie_value


class CardRenewalPage(RawPage):
    pass


class StatusPage(LoggedPage, PartialHTMLPage):
    def on_load(self):
        # sometimes checking accounts are missing
        msg = CleanText('//div[has-class("alert--danger")]', default=None)(self.doc)
        if msg:
            raise BrowserUnavailable(msg)


class AccountsPage(LoggedPage, HTMLPage):
    ENCODING = 'utf-8'

    def is_here(self):
        # This id appears when there are no accounts (pro and pp)
        return not self.doc.xpath('//div[contains(@id, "alert-random")]')

    ACCOUNT_TYPES = {
        'comptes courants': Account.TYPE_CHECKING,
        'cav': Account.TYPE_CHECKING,
        'livret': Account.TYPE_SAVINGS,
        'livret-a': Account.TYPE_SAVINGS,
        'pel': Account.TYPE_SAVINGS,
        'cel': Account.TYPE_SAVINGS,
        'ldd': Account.TYPE_SAVINGS,
        'csl': Account.TYPE_SAVINGS,
        'comptes épargne': Account.TYPE_SAVINGS,
        'mon épargne': Account.TYPE_SAVINGS,
        'csljeune': Account.TYPE_SAVINGS,  # in url
        'ord': Account.TYPE_MARKET,
        'comptes bourse': Account.TYPE_MARKET,
        'mes placements financiers': Account.TYPE_MARKET,
        'cefp': Account.TYPE_MARKET,
        'av': Account.TYPE_LIFE_INSURANCE,
        'assurances vie': Account.TYPE_LIFE_INSURANCE,
        'assurance-vie': Account.TYPE_LIFE_INSURANCE,
        'mes crédits': Account.TYPE_LOAN,
        'crédit': Account.TYPE_LOAN,
        'prêt': Account.TYPE_LOAN,
        'pea': Account.TYPE_PEA,
        'carte': Account.TYPE_CARD,
        'per': Account.TYPE_PER,
        'compte à terme': Account.TYPE_DEPOSIT,
    }

    ACCOUNTS_OWNERSHIP = {
        'Comptes de mes enfants': AccountOwnership.ATTORNEY,
        'joint': AccountOwnership.CO_OWNER,
        'commun': AccountOwnership.CO_OWNER,
    }

    @method
    class iter_accounts(ListElement):
        item_xpath = '//table[@class="table table--accounts"]/tr[has-class("table__line--account") and count(descendant::td) > 1 and @data-line-account-href]'

        class item(ItemElement):
            klass = Account

            def condition(self):
                # Ignore externally aggregated accounts and insurances:
                # We need to use 'assurance/' as a filter because using 'assurance' would filter out life insurance accounts
                return not self.is_external() and 'assurance/' not in Field('url')(self)

            obj_label = CleanText('.//a[has-class("account--name")] | .//div[has-class("account--name")]')
            obj_currency = FrenchTransaction.Currency('.//a[has-class("account--balance")]')

            obj__holder = None

            obj__amount = CleanDecimal.French('.//a[has-class("account--balance")]')

            def obj_balance(self):
                if Field('type')(self) != Account.TYPE_CARD:
                    balance = Field('_amount')(self)
                    return balance
                return Decimal('0')

            def obj_coming(self):
                # report deferred expenses in the coming attribute
                if Field('type')(self) == Account.TYPE_CARD:
                    return Field('_amount')(self)

            def obj_type(self):
                # card url is /compte/cav/xxx/carte/yyy so reverse to match "carte" before "cav"
                for word in Field('url')(self).lower().split('/')[::-1]:
                    # card url can contains creditcardkey as query params
                    # 'mouvements-a-venir?selection=deferred&creditcardkey=xxxxx'
                    if not word.find('creditcardkey') == -1:
                        return Account.TYPE_CARD
                    account_type = self.page.ACCOUNT_TYPES.get(word)
                    if account_type:
                        return account_type

                account_type = MapIn(Lower(Field('label')), self.page.ACCOUNT_TYPES, Account.TYPE_UNKNOWN)(self)
                if account_type:
                    return account_type

                for word in Field('label')(self).replace('_', ' ').lower().split():
                    account_type = self.page.ACCOUNT_TYPES.get(word)
                    if account_type:
                        return account_type

                category = CleanText('./preceding-sibling::tr[has-class("list--accounts--master")]//h4')(self)
                account_type = self.page.ACCOUNT_TYPES.get(category.lower())
                if account_type:
                    return account_type

                return Account.TYPE_UNKNOWN

            def obj_id(self):
                account_type = Field('type')(self)
                if account_type == Account.TYPE_CARD:
                    # When card is opposed it still appears on accounts page with a dead link and so, no id. Skip it.
                    if Attr('.//a[has-class("account--name")]', 'href')(self) == '#':
                        raise SkipItem()
                    return self.obj__idparts()[1]

            def obj_ownership(self):
                ownership = Coalesce(
                    MapIn(
                        CleanText('../tr[contains(@class, "list--accounts--master")]//h4/text()'),
                        self.page.ACCOUNTS_OWNERSHIP,
                        default=NotAvailable
                    ),
                    MapIn(
                        Lower(Field('label')),
                        self.page.ACCOUNTS_OWNERSHIP,
                        default=NotAvailable
                    ),
                    default=NotAvailable
                )(self)

                return ownership

            def obj_url(self):
                link = Attr('.//a[has-class("account--name")] | .//a[2] | .//div/a', 'href', default=NotAvailable)(self)
                return urljoin(self.page.url, link)

            def is_external(self):
                return '/budget/' in Field('url')(self) or '/crypto/' in Field('url')(self)

            def obj__idparts(self):
                return re.findall(r'[a-z\d]{32}', Field('url')(self))

            def obj__webid(self):
                parts = self.obj__idparts()
                if parts:
                    return parts[0]


class CATPage(LoggedPage, HTMLPage):
    @method
    class fill_account(ItemElement):
        def condition(self):
            return not HasElement('//div[contains(@class, "alert") and contains(text(), "indisponible")]')(self)

        obj_id = obj_number = CleanText('//h3[has-class("c-product-title__sublabel")]')
        obj_balance = CleanDecimal.French('//div[contains(text(), "Solde au ")]/following-sibling::div')
        obj_currency = CleanCurrency('//div[contains(text(), "Solde au ")]/following-sibling::div')


class LoanPage(LoggedPage, HTMLPage):
    LOAN_TYPES = {
        'paiement-3x': Account.TYPE_CONSUMER_CREDIT,
        'consommation': Account.TYPE_CONSUMER_CREDIT,
        'immobilier': Account.TYPE_MORTGAGE,
    }

    @method
    class fill_account(ItemElement):
        def obj_id(self):
            account_id = Coalesce(
                Regexp(
                    CleanText('//*[has-class("account-number")]', transliterate=True),
                    r'Reference du compte : (\d+)', default=NotAvailable
                ),
                CleanText(
                    '//h3[has-class("c-product-title__sublabel")]',
                    default=NotAvailable
                ),
                default=NotAvailable
            )(self)
            assert not empty(account_id), "Could not fetch account ID, xpath was not found."
            return account_id

        obj_type = Account.TYPE_LOAN

    @method
    class get_loan(ItemElement):

        klass = Loan

        # The xpath was changed, resulting in accounts without ids.
        obj_id = Coalesce(
            Regexp(
                CleanText('//h3[contains(@class, "account-number")]/strong', transliterate=True),
                r'Reference du compte : (\d+)',
                default=NotAvailable
            ),
            CleanText(
                '//h3[contains(@class, "c-product-title__sublabel")]',
                default=NotAvailable
            ),
        )
        obj_label = CleanText(r'//span[@class="account-edit-label"]/span[1]')
        obj_currency = CleanCurrency('//p[contains(text(), "Solde impayé")]/span')
        # Loan rate seems to be formatted as '1,123 %' or as '1.123 %' depending on connections
        obj_rate = Coalesce(
            CleanDecimal.French('//p[contains(text(), "Taux nominal")]/span', default=NotAvailable),
            CleanDecimal.SI('//p[contains(text(), "Taux nominal")]/span', default=NotAvailable),
            CleanDecimal.French('//div[contains(text(), "Taux nominal")]/following-sibling::div', default=NotAvailable),
            CleanDecimal.SI('//div[contains(text(), "Taux nominal")]/following-sibling::div', default=NotAvailable),
            default=NotAvailable
        )
        obj_nb_payments_left = Eval(
            float_to_int,
            CleanDecimal.French('//p[contains(text(), "échéances restantes")]/span', default=NotAvailable)
        )
        obj_next_payment_amount = Coalesce(
            CleanDecimal.French(
                '//p[contains(text(), "Montant de la prochaine échéance")]/span',
                default=NotAvailable
            ),
            CleanDecimal.French(
                '//div[contains(text(), "Montant de la prochaine échéance")]/following-sibling::div',
                default=NotAvailable
            ),
            default=NotAvailable
        )

        obj_nb_payments_total = Eval(int, CleanDecimal.French('//p[contains(text(), "ances totales") or contains(text(), "Nombre total")]/span'))
        obj_subscription_date = Date(
            CleanText('//p[contains(text(), "Date de départ du prêt")]/span'),
            parse_func=parse_french_date
        )

        obj_total_amount = Coalesce(
            CleanDecimal.French(
                '//p[matches(text(), "(Capital|Montant) emprunt")]/span',
                default=NotAvailable
            ),
            CleanDecimal.French(
                '//div[matches(text(), "(Capital|Montant) (E|e)mprunt")]/following-sibling::div',
                default=NotAvailable
            ),
        )

        obj_insurance_amount = CleanDecimal.French(
            '//p[contains(text(), "Montant en vigueur de la prime")]/span',
            default=NotAvailable,
        )

        obj_next_payment_date = Date(
            CleanText('//div[contains(text(), "Prochaine échéance")]/following-sibling::div'),
            dayfirst=True,
            default=NotAvailable
        )

        obj_maturity_date = Date(
            CleanText('//div[text()="Date prévisionelle d\'échéance finale"]/following-sibling::div'),
            dayfirst=True,
            default=NotAvailable
        )

        def obj_balance(self):
            balance = Coalesce(
                CleanDecimal.French(
                    '//div[contains(text(), "Capital restant dû")]/following-sibling::div', default=None
                ),
                CleanDecimal.French(
                    '//p[contains(text(), "Capital restant dû")]//span', default=None
                ),
            )(self)
            if balance > 0:
                balance *= -1
            return balance

        def obj_type(self):
            # fetch loan type from url
            return MapIn(self, self.page.LOAN_TYPES, Account.TYPE_LOAN).filter(self.page.url)


class NoAccountPage(LoggedPage, HTMLPage):
    def is_here(self):
        err = CleanText('//div[contains(@id, "alert-random")]/text()', children=False)(self.doc)
        return "compte inconnu" in err.lower()


class CardCalendarPage(LoggedPage, RawPage):
    def is_here(self):
        return b'VCALENDAR' in self.doc

    def on_load(self):
        page_content = self.content.decode('utf-8')
        self.browser.deferred_card_calendar = []
        self.browser.card_calendar_loaded = True

        # handle ics calendar
        dates = page_content.split('BEGIN:VEVENT')[1:]
        assert len(dates) % 2 == 0, 'List length should be even-numbered'

        # get all dates
        dates = [re.search(r'(?<=VALUE\=DATE:)(\d{8})', el).group(1) for el in dates]
        dates.sort()

        for i in range(0, len(dates), 2):
            if len(dates[i:i + 2]) == 2:
                # list contains tuple like (vdate, date)
                self.browser.deferred_card_calendar.append(
                    (
                        Date().filter(dates[i]),
                        Date().filter(dates[i + 1]),
                    )
                )


class CalendarPage(LoggedPage, HTMLPage):
    def on_load(self):
        # redirect
        calendar_ics_url = urljoin(
            self.browser.BASEURL,
            CleanText('//a[contains(@href, "calendrier.ics")]/@href')(self.doc)
        )
        self.browser.location(calendar_ics_url)


def otp_pagination(func):
    @wraps(func)
    def inner(page, *args, **kwargs):
        while True:
            try:
                for r in func(page, *args, **kwargs):
                    yield r
            except NextPage as e:
                result = page.browser.otp_location(e.request)
                if result is None:
                    return

                page = result.page
            else:
                return

    return inner


class HistoryPage(LoggedPage, HTMLPage):
    """
    be carefull : `transaction_klass` is used in another page
    of an another module which is an abstract of this page
    """
    transaction_klass = Transaction

    @method
    class fill_account(ItemElement):
        def obj_id(self):
            if self.obj.type == Account.TYPE_CARD:
                return self.obj.id

            account_id = Coalesce(
                Regexp(
                    CleanText('//*[has-class("account-number")]', transliterate=True),
                    r'Reference du compte : (\d+)', default=NotAvailable
                ),
                CleanText('//h3[@class="c-product-title__sublabel"]', default=NotAvailable),
                default=NotAvailable
            )(self)
            assert not empty(account_id), "Could not fetch account ID, xpath was not found."
            return account_id

        def obj__key(self):
            if self.obj.type == Account.TYPE_CARD:
                # trying to retrive  account key_id from the URL parameters
                parsed_url = urlparse(self.page.url)
                account_key = parse_qs(parsed_url.query).get('creditCardKey', [''])[0]
                if account_key:
                    return account_key

                # Not tested for other account types.
                account_key = Coalesce(
                    Attr('//div[@data-action="check"]', 'data-account-key', default=NotAvailable),

                    Regexp(
                        Attr('//*[contains(@id, "hinclude__") and contains(@src, "mes-produits/")]', 'src'),
                        r'(\w+)$',
                        default=NotAvailable
                    ),
                    default=NotAvailable
                )(self)
                assert not empty(account_key), 'Could not fetch account key, xpath was not found.'
                return account_key

        def obj_coming(self):
            if self.obj.type == Account.TYPE_CARD:
                return self.obj.coming
            return CleanDecimal.French(
                '//li[h4[text()="Mouvements à venir"]]/h3',
                default=NotAvailable
            )(self)

    @otp_pagination
    @method
    class iter_history(ListElement):
        item_xpath = '''
            //ul[has-class("list__movement")]/li[div and not(contains(@class, "summary"))
                and not(contains(@class, "graph"))
                and not(contains(@class, "separator"))
                and not(contains(@class, "list__movement__line--deffered"))]
        '''

        def next_page(self):
            next_page = self.el.xpath('//li[has-class("list__movement__range-summary")]')
            if next_page:
                next_page_token = Attr('.', 'data-operations-next-pagination')(next_page[0])
                params = {
                    'rumroute': 'accounts.bank.movements',
                    'continuationToken': next_page_token,
                }
                parsed = urlparse(self.page.url)
                return '%s://%s%s?%s' % (parsed.scheme, parsed.netloc, parsed.path, urlencode(params))

        class item(ItemElement):
            klass = Transaction

            def condition(self):
                # Users can split their transactions if they want. We don't want this kind
                # of custom transaction because:
                #  - The sum of this transactions can be different than the original transaction
                #     ex: The real transaction as an amount of 100€, the user is free to split it on 50€ and 60€
                #  - The original transaction is scraped anyway and we don't want duplicates
                return not self.xpath('./div[has-class("list__movement__line--block__split")]')

            def obj_amount(self):
                if self.xpath('.//div[has-class("list-operation-item__split-picto")]'):
                    # The transaction is split, so the XPath to get the transaction amount will return
                    # 1 + n-split elements. We only want the transaction total amount which is the first element
                    return CleanDecimal.French('(.//div[has-class("list-operation-item__amount")])[1]')(self)
                return CleanDecimal.French('.//div[has-class("list-operation-item__amount")]')(self)

            obj_category = CleanText('.//span[contains(@class, "category")]')
            obj__account_name = CleanText('.//span[contains(@class, "account__name-xs")]', default=None)
            obj_raw = Transaction.Raw(
                Coalesce(
                    CleanText('.//span[matches(@class, "list__movement--label-(initial|user)")]'),
                    CleanText('.//div[has-class("list-operation-item__label-name")]')
                )
            )

            def obj_id(self):
                if Field('_is_coming')(self):
                    # discard transaction.id because some "authorization" transactions are strictly
                    # identical (same label, ID, date and amount, nothing to discriminate).
                    # The website, once these transactions get a booked status, gives them a proper distinct ID.
                    return ""
                return (
                    Attr('.', 'data-id', default=NotAvailable)(self)
                    or Attr('.', 'data-custom-id', default=NotAvailable)(self)
                    or ""
                )

            def obj_type(self):
                # In order to set TYPE_DEFERRED_CARD transactions correctly,
                # we must check if the transaction's account_name is in the list
                # of deferred cards, but summary transactions must escape this rule.
                if self.obj.type == Transaction.TYPE_CARD_SUMMARY:
                    return self.obj.type

                deferred_card_labels = [card.label for card in self.page.browser.cards_list]
                if Upper(Field('_account_name'))(self) in deferred_card_labels:
                    return Transaction.TYPE_DEFERRED_CARD

                is_card = Env('is_card', default=False)(self)
                if is_card:
                    if 'CARTE' in self.obj.raw:
                        return Transaction.TYPE_DEFERRED_CARD
                else:
                    if Env('coming', default=False)(self) and Field('raw')(self).startswith('CARTE '):
                        return Transaction.TYPE_CARD_SUMMARY

                # keep the value previously set by Transaction.Raw
                return self.obj.type

            def obj_bdate(self):
                if Env('is_card', default=False)(self):
                    bdate = Date(
                        CleanText('./preceding-sibling::li[contains(@class, "date-line")][1]', transliterate=True),
                        parse_func=parse_french_date,
                    )(self)
                    return bdate
                return Field('date')(self)

            def obj_rdate(self):
                if self.obj.rdate:
                    # Transaction.Raw may have already set it
                    return self.obj.rdate

                s = Regexp(Field('raw'), r' (\d{2}/\d{2}/\d{2}) | (?!NUM) (\d{6}) ', default=NotAvailable)(self)
                if not s:
                    return Field('date')(self)
                s = s.replace('/', '')
                # Sometimes the user enters an invalid date 16/17/19 for example
                return Date(dayfirst=True, default=NotAvailable).filter('%s-%s-%s' % (s[:2], s[2:4], s[4:]))

            def obj__is_coming(self):
                return (
                    Env('coming', default=False)(self)
                    or len(self.xpath('.//span[@title="Mouvement à débit différé"]'))
                    or len(
                        self.xpath('.//div[has-class("list-operation-item__label-name--authorization")]')
                    )
                    or self.obj_date() > datetime.date.today()
                )

            def obj_date(self):
                # Months with accents are retrieved like that: f\xe9vrier
                date = Date(
                    CleanText('./preceding-sibling::li[contains(@class, "date-line")][1]', transliterate=True),
                    parse_func=parse_french_date,
                )(self)

                if Env('is_card', default=False)(self):
                    if self.page.browser.deferred_card_calendar is None and self.page.browser.card_calendar_loaded:
                        self.page.browser.location(Link('//a[contains(text(), "calendrier")]')(self))
                    else:
                        has_coming = HasElement(
                            '//div[@data-operations-debit-informations=""]//span[contains(text(), "Montant total des débits")]'
                        )(self)

                        if has_coming:
                            date = Date(
                                CleanText('//div[@data-operations-debit-informations=""]//span[contains(text(), "Montant total")]//span[1]'),
                                parse_func=parse_french_date,
                            )(self)
                            return date
                    closest = self.page.browser.get_debit_date(date)
                    if closest:
                        return closest
                return date

            def obj__card_sum_detail_link(self):
                if Field('type')(self) == Transaction.TYPE_CARD_SUMMARY:
                    return Attr('.//div', 'data-action-url')(self.el)
                return NotAvailable

            def validate(self, obj):
                # TYPE_DEFERRED_CARD transactions are already present in the card history
                # so we only return TYPE_DEFERRED_CARD for the coming:
                if not Env('coming', default=False)(self):
                    is_card = Env('is_card', default=False)(self)
                    return (
                        is_card or (
                            not len(self.xpath('.//span[has-class("icon-carte-bancaire")]'))
                            and not len(self.xpath('.//a[contains(@href, "/carte")]'))
                            and obj.type != Transaction.TYPE_DEFERRED_CARD
                        )
                    )
                elif Env('coming', default=False)(self):
                    # Do not return coming from deferred cards if their
                    # summary does not have a fixed amount yet:
                    return obj.type != Transaction.TYPE_CARD_SUMMARY
                else:
                    return True

    def get_cards_number_link(self):
        return Link('//a[small[span[contains(text(), "carte bancaire")]]]', default=NotAvailable)(self.doc)

    def get_csv_link(self):
        return Link(
            '//a[@data-operations-export-button and not(has-class("hidden"))]',
            default=None
        )(self.doc)

    def get_calendar_link(self):
        # CleanText needed because there's whitespaces and linebreaks in the href attribute
        # Such as:
        # <a data-url="accounts.bank.deferred_card.calendar" href="                            /compte/cav/11b11111111111111111111111111/carte/b111111111111111/calendrier
        #            ">
        return CleanText(Link('//a[contains(text(), "calendrier")]'))(self.doc)


class CardSumDetailPage(LoggedPage, HTMLPage):
    @otp_pagination
    @method
    class iter_history(ListElement):
        item_xpath = '//li[contains(@class, "deffered")]'  # this quality website's got all-you-can-eat typos!

        class item(ItemElement):
            klass = Transaction

            obj_amount = CleanDecimal.French('.//div[has-class("list-operation-item__amount")]')
            obj_raw = Transaction.Raw(CleanText('.//div[has-class("list-operation-item__label-name")]'))
            obj_id = Attr('.', 'data-id')
            obj__is_coming = False
            obj_category = CleanText('.//span[has-class("list-operation-item__category")]')

            def obj_type(self):
                # to override CARD typing done by obj.raw
                return Transaction.TYPE_DEFERRED_CARD


class CardHistoryPage(LoggedPage, CsvPage):
    ENCODING = 'latin-1'
    FMTPARAMS = {'delimiter': str(';')}
    HEADER = 1

    @method
    class iter_history(DictElement):
        class item(ItemElement):
            klass = Transaction

            obj_raw = Transaction.Raw(Dict('label'))
            obj_bdate = Date(Dict('dateOp'))

            def obj_date(self):
                return self.page.browser.get_debit_date(Field('bdate')(self))

            obj__account_label = Dict('accountLabel')
            obj__is_coming = False

            def obj_amount(self):
                if Field('type')(self) == Transaction.TYPE_CARD_SUMMARY:
                    # '-' so the reimbursements appear positively in the card transactions:
                    return -CleanDecimal.French(Dict('amount'))(self)
                return CleanDecimal.French(Dict('amount'))(self)

            def obj_rdate(self):
                if self.obj.rdate:
                    # Transaction.Raw may have already set it
                    return self.obj.rdate

                s = Regexp(Field('raw'), r' (\d{2}/\d{2}/\d{2}) | (?!NUM) (\d{6}) ', default=NotAvailable)(self)
                if not s:
                    return Field('date')(self)
                s = s.replace('/', '')
                # Sometimes the user enters an invalid date 16/17/19 for example
                return Date(dayfirst=True, default=NotAvailable).filter('%s%s%s%s%s' % (s[:2], '-', s[2:4], '-', s[4:]))

            def obj_type(self):
                if 'CARTE' in self.obj.raw:
                    return Transaction.TYPE_DEFERRED_CARD
                return self.obj.type

            def obj_category(self):
                return Dict('category')(self)


class Myiter_investment(TableElement):
    # We do not scrape the investments contained in the "Engagements en liquidation" table
    # so we must check that the <h3> before the <div><table> does not contain this title.
    # Also we do not want to scrape the investments contained in "Gestion Profilée" at the same time
    # as the other table as it do not have the same number of columns
    item_xpath = '//div[preceding-sibling::h3[1][text()!="Engagements en liquidation" and text()!="Gestion Profilée"]]//table[contains(@class, "operations") or @data-table-trading-operations=""]/tbody/tr'
    head_xpath = '//div[preceding-sibling::h3[1][text()!="Engagements en liquidation" and text()!="Gestion Profilée"]]//table[contains(@class, "operations") or @data-table-trading-operations=""]/thead/tr/th'

    col_label = 'VALEUR'
    col_valuation = 'MONTANT'
    col_quantity = 'QUANTITÉ'
    col_unitvalue = 'COURS'


class Myitem(ItemElement):
    klass = Investment

    obj_label = Coalesce(
        Base(TableCell('label'), CleanText('.//span[@class="c-link__label "]')),
        CleanText('.//strong', children=False),  # for investments without link
        CleanText('.//span[@class="u-ellipsis " and @title]'),  # Needed for some "Fonds Euro" or "Support" investments
        default=NotAvailable
    )

    obj_valuation = CleanDecimal.French(TableCell('valuation'))
    obj_quantity = CleanDecimal.French(TableCell('quantity'), default=NotAvailable)
    obj_unitvalue = CleanDecimal.French(TableCell('unitvalue'), default=NotAvailable)
    obj_code = Coalesce(
        Base(TableCell('label'), IsinCode(CleanText('./span'), default=NotAvailable)),
        Base(TableCell('label'), IsinCode(CleanText('.//span[@class="c-table__mention"]'), default=NotAvailable)),
        default=NotAvailable
    )
    obj_code_type = IsinType(Field('code'))


def my_pagination(func):
    def inner(page, *args, **kwargs):
        while True:
            try:
                for r in func(page, *args, **kwargs):
                    yield r
            except NextPage as e:
                try:
                    result = page.browser.location(e.request)
                    page = result.page
                except BrowserHTTPNotFound as e:
                    page.logger.warning(e)
                    return
            else:
                return
    return inner


MARKET_ORDER_TYPES = {
    'LIM': MarketOrderType.LIMIT,
    'AM': MarketOrderType.MARKET,
    'ASD': MarketOrderType.TRIGGER,
}

MARKET_DIRECTIONS = {
    'Achat': MarketOrderDirection.BUY,
    'Vente': MarketOrderDirection.SALE,
}

MARKET_ORDER_PAYMENTS = {
    'Comptant': MarketOrderPayment.CASH,
    'Règlement différé': MarketOrderPayment.DEFERRED,
}


class MarketPage(LoggedPage, HTMLPage):
    @method
    class fill_account(ItemElement):
        def condition(self):
            return not HasElement('//div[contains(@class, "alert") and contains(text(), "indisponible")]')(self)

        def obj_id(self):
            account_id = Coalesce(
                Regexp(
                    CleanText('//*[has-class("account-number")]', transliterate=True),
                    r'Reference du compte : (\d+)', default=NotAvailable
                ),
                CleanText(
                    '//h3[has-class("c-product-title__sublabel")]',
                    default=NotAvailable
                ),
                default=NotAvailable
            )(self)
            assert not empty(account_id), 'Could not fetch account ID, xpath was not found.'
            return account_id

        obj_number = obj_id

        obj_valuation_diff = (CleanDecimal.French(
            Regexp(
                CleanText('//div[contains(text(), "+/- values")]/following-sibling::div'),
                r'(.*?€)',
                default=NotAvailable
            ),
            default=NotAvailable
        ))

        def obj_valuation_diff_ratio(self):
            # For some accounts, this value is given on the same line as valuation_diff
            # sometimes it has its own line
            v_diff_ratio = CleanDecimal.French(
                Coalesce(
                    Regexp(
                        CleanText('//div[contains(text(), "+/- values")]/following-sibling::div'),
                        r'\(([^)]+)\)',
                        default=NotAvailable
                    ),
                    CleanText(
                        '//div[contains(text(), "+/- values en %")]/following-sibling::div'
                    ),
                    default=NotAvailable,
                ),
                default=NotAvailable
            )(self)

            if not empty(v_diff_ratio):
                return v_diff_ratio / 100
            return NotAvailable

        def obj_balance(self):
            # balance parsed on the dashboard might not be the most up to date value
            # for market accounts
            updated_balance = self.page.get_balance(self.obj.type)
            if updated_balance is not None:
                return updated_balance
            return self.obj.balance

    def get_balance(self, account_type):
        if account_type == Account.TYPE_LIFE_INSURANCE:
            txt = "Solde au"
        else:
            txt = "Total Portefeuille"
        # HTML tags are usually h4-h3 but may also be span-span
        h_balance = CleanDecimal('//li[h4[contains(text(), "%s")]]/h3' % txt, replace_dots=True, default=None)(self.doc)
        span_balance = CleanDecimal(
            '//li/span[contains(text(), "%s")]/following-sibling::span' % txt,
            replace_dots=True, default=None
        )(self.doc)
        return h_balance or span_balance or None

    def get_market_order_link(self):
        # CleanText needed because there's whitespaces and linebreaks in the href attribute
        # Such as:
        # <a data-url="accounts.trading.ord.positions" href="                            /compte/ord/1a11111111111111111111111/positions
        #           ">
        return CleanText(Link('//a[contains(@data-url, "orders")]', default=''))(self.doc)

    @my_pagination
    @method
    class iter_history(TableElement):
        item_xpath = '//table/tbody/tr'
        head_xpath = '//table/thead/tr/th'

        col_label = ['Nature', 'Opération']
        col_amount = 'Montant'
        col_date = ["Date d'effet", 'Date', 'Date opération']

        next_page = Link('//li[@class="pagination__next"]/a')

        class item(ItemElement):
            klass = Transaction

            def obj_date(self):
                d = Date(CleanText(TableCell('date')), dayfirst=True, default=None)(self)
                if d:
                    return d
                return Date(CleanText(TableCell('date')), parse_func=parse_french_date)(self)

            obj_raw = Transaction.Raw(CleanText(TableCell('label')))
            obj_amount = CleanDecimal(TableCell('amount'), replace_dots=True, default=NotAvailable)
            obj__is_coming = False

            def parse(self, el):
                if el.xpath('./td[2]/a'):
                    m = re.search(r'(\d+)', el.xpath('./td[2]/a')[0].get('data-modal-alert-behavior', ''))
                    if m:
                        url = '%s%s%s' % (self.page.url.split('mouvements')[0], 'mouvement/', m.group(1))
                        page = self.page.browser.open(url).page
                        self.env['account']._history_pages.append((Field('raw')(self), page))
                        raise SkipItem()

            def validate(self, obj):
                # "Nouvelle allocation de profil" transactions have no amount
                # as well as some "Frais de gestion" transactions.
                return not empty(obj.amount)

    @method
    class iter_investment(Myiter_investment):
        col_unitprice = 'Px. Revient'
        col_diff = '+/- latentes'

        class item(Myitem):
            obj_unitprice = CleanDecimal.French(TableCell('unitprice'), default=NotAvailable)
            obj_diff = CleanDecimal.French(TableCell('diff'), default=NotAvailable)
            obj_unitvalue = Coalesce(
                CleanDecimal.French(
                    Base(TableCell('unitvalue'), CleanText('./span[not(@class)]')),
                    default=NotAvailable,
                ),
                CleanDecimal.French(
                    Base(TableCell('unitvalue'), CleanText('.//span[contains(@class, "u-ellipsis")]')),
                    default=NotAvailable),
                default=NotAvailable
            )

    @method
    class _iter_investment_gestion_profilee(Myiter_investment):
        item_xpath = '//div[preceding-sibling::h3[1][text()="Gestion Profilée"]]//table[contains(@class, "operations") or @data-table-trading-operations=""]/tbody/tr'
        head_xpath = '//div[preceding-sibling::h3[1][text()="Gestion Profilée"]]//table[contains(@class, "operations") or @data-table-trading-operations=""]/thead/tr/th'

        col_unitprice = 'Px. Revient'
        col_diff = '+/- latentes'

        class item(Myitem):
            obj_unitprice = CleanDecimal.French(TableCell('unitprice'), default=NotAvailable)
            obj_diff = CleanDecimal.French(TableCell('diff'), default=NotAvailable)
            obj_unitvalue = CleanDecimal.French(
                Base(TableCell('unitvalue'), CleanText('./span[not(@class)]')),
                default=NotAvailable
            )

    def has_gestion_profilee(self):
        return HasElement('//div[preceding-sibling::h3[1][text()="Gestion Profilée"]]')(self.doc)

    def get_liquidity(self):
        # Xpath can be h3/h4 or div/span; in both cases
        # the first node contains "Solde Espèces":
        valuation = Coalesce(
            CleanDecimal.French(
                '//li/*[contains(text(), "Solde Espèces")]/following-sibling::*',
                default=NotAvailable
            ),
            CleanDecimal.French(
                '//div[@class="u-height-full "]//div[contains(text(),"Solde Espèces")]/following-sibling::div',
                default=NotAvailable
            ),
            default=NotAvailable
        )(self.doc)

        if not empty(valuation):
            return create_french_liquidity(valuation)

    def get_transactions_from_detail(self, account):
        for label, page in account._history_pages:
            amounts = page.doc.xpath('//span[contains(text(), "Montant")]/following-sibling::span')
            if len(amounts) == 3:
                amounts.pop(0)
            for table in page.doc.xpath('//table'):
                t = Transaction()

                t.date = Date(
                    CleanText(page.doc.xpath('//span[contains(text(), "Date d\'effet")]/following-sibling::span')),
                    dayfirst=True
                )(page)
                t.label = label
                t.amount = CleanDecimal(replace_dots=True).filter(amounts[0])
                amounts.pop(0)
                t._is_coming = False
                t.investments = []
                sum_amount = 0
                for tr in table.xpath('./tbody/tr'):
                    i = Investment()
                    i.label = CleanText().filter(tr.xpath('./td[1]'))
                    i.vdate = Date(CleanText(tr.xpath('./td[2]')), dayfirst=True)(tr)
                    i.unitvalue = CleanDecimal(replace_dots=True).filter(tr.xpath('./td[3]'))
                    i.quantity = CleanDecimal(replace_dots=True).filter(tr.xpath('./td[4]'))
                    i.valuation = CleanDecimal(replace_dots=True).filter(tr.xpath('./td[5]'))
                    sum_amount += i.valuation
                    t.investments.append(i)

                if t.label == 'prélèvement':
                    t.amount = sum_amount

                yield t

    @pagination
    @method
    class iter_market_orders(TableElement):
        item_xpath = '//table/tbody/tr[td]'
        head_xpath = '//table/thead/tr/th'

        col_date = 'Date'
        col_label = 'Libellé'
        col_direction = 'Sens'
        col_state = re.compile('[ÉE]tat')
        col_quantity = 'Qté'
        col_order_type = 'Type'
        col_unitvalue = 'Cours'
        col_validity_date = 'Validité'
        col_stock_market = 'Marché'

        next_page = Link('//li[@class="pagination__next"]//a', default=None)

        class item(ItemElement):
            klass = MarketOrder

            obj_id = Base(TableCell('date'), CleanText('.//a'))
            obj_label = CleanText(TableCell('label'), children=False)
            obj_direction = Map(CleanText(TableCell('direction')), MARKET_DIRECTIONS, MarketOrderDirection.UNKNOWN)
            obj_code = IsinCode(Base(TableCell('label'), CleanText('.//a')))
            obj_currency = CleanCurrency(TableCell('unitvalue'))

            # The column contains the payment_method and the stock market (e.g. 'Comptant Euronext')
            # We select the stock_market by using the <br> between the two.
            obj_stock_market = Base(
                TableCell('stock_market'),
                CleanText('./text()[2]'),
                default=NotAvailable
            )
            obj_payment_method = MapIn(
                CleanText(TableCell('stock_market')),
                MARKET_ORDER_PAYMENTS,
                MarketOrderPayment.UNKNOWN
            )

            # Unitprice may be absent if the order is still ongoing
            obj_unitprice = CleanDecimal.US(TableCell('state'), default=NotAvailable)
            obj_unitvalue = CleanDecimal.French(TableCell('unitvalue'), default=NotAvailable)
            obj_ordervalue = CleanDecimal.French(TableCell('order_type'), default=NotAvailable)
            obj_quantity = CleanDecimal.SI(TableCell('quantity'))

            obj_date = Date(Base(TableCell('date'), CleanText('.//span')), dayfirst=True)
            obj_validity_date = Date(CleanText(TableCell('validity_date')), dayfirst=True)

            # Text format looks like 'LIM 49,000', we only use the 'LIM' for typing
            obj_order_type = MapIn(CleanText(TableCell('order_type')), MARKET_ORDER_TYPES, MarketOrderType.UNKNOWN)
            # Text format looks like 'Exécuté 12.345 $' or 'En cours', we only fetch the first words
            obj_state = CleanText(Regexp(CleanText(TableCell('state')), r'^(\D+)'))


class SavingMarketPage(MarketPage):
    @pagination
    @method
    class iter_history(TableElement):
        item_xpath = '//table/tbody/tr'
        head_xpath = '//table/thead/tr/th'

        col_label = 'Opération'
        col_amount = 'Montant'
        col_date = 'Date opération'
        col_vdate = 'Date Valeur'

        next_page = Link('//li[@class="pagination__next"]/a')

        class item(ItemElement):
            klass = Transaction

            obj_label = CleanText(TableCell('label'))
            obj_amount = CleanDecimal(TableCell('amount'), replace_dots=True)
            obj__is_coming = False

            def obj_date(self):
                return parse_french_date(CleanText(TableCell('date'))(self))

            def obj_vdate(self):
                return parse_french_date(CleanText(TableCell('vdate'))(self))

    @method
    class iter_investment(TableElement):
        item_xpath = '//table/tbody/tr[count(descendant::td) > 4]'
        head_xpath = '//table/thead/tr[count(descendant::th) > 4]/th'

        col_label = 'Fonds'
        col_code = 'Code Isin'
        col_unitvalue = 'Valeur de la part'
        col_quantity = 'Nombre de parts'
        col_vdate = 'Date VL'

        class item(ItemElement):
            klass = Investment

            obj_label = CleanText(TableCell('label'))
            obj_code = IsinCode(CleanText(TableCell('code')))
            obj_code_type = IsinType(CleanText(TableCell('code')))
            obj_unitvalue = CleanDecimal.French(TableCell('unitvalue'))
            obj_quantity = CleanDecimal.French(TableCell('quantity'))
            obj_valuation = Eval(lambda x, y: x * y, Field('quantity'), Field('unitvalue'))
            obj_vdate = Date(CleanText(TableCell('vdate')), dayfirst=True)


class PerPage(MarketPage):
    @method
    class iter_history(TableElement):
        item_xpath = '//table[@class="table "]/tbody/tr'
        head_xpath = '//table[@class="table "]/thead/tr/th'

        col_label = 'Nature'
        col_amount = 'Montant'
        col_date = 'Date'

        class item(ItemElement):
            klass = Transaction

            def condition(self):
                return bool(CleanText(TableCell('amount'))(self))

            obj_raw = Regexp(CleanText(TableCell('label')), r'(^.*?)Fermer Détail')
            obj_amount = CleanDecimal.French(TableCell('amount'))
            obj_date = Date(CleanText(TableCell('date'), default=NotAvailable), dayfirst=True)
            obj__is_coming = False

    @method
    class iter_investment(Myiter_investment):
        item_xpath = '//div[contains(@class, "trading-operations")]//table/tbody/tr'
        head_xpath = '//div[contains(@class, "trading-operations")]//table/thead/tr/th'

        class item(Myitem):
            pass


class AsvPage(MarketPage):
    @method
    class iter_investment(Myiter_investment):
        col_vdate = 'Date de Valeur'
        col_unitprice = 'Px. Revient'
        col_diff = '+/- latentes'

        class item(Myitem):
            obj_diff = CleanDecimal.French(TableCell('diff'), default=NotAvailable)
            obj_unitprice = CleanDecimal.French(TableCell('unitprice'), default=NotAvailable)
            obj_vdate = Date(CleanText(TableCell('vdate')), dayfirst=True, default=NotAvailable)

    def fetch_opening_date(self):
        return Date(
            CleanText('//div[contains(text(), "ouverture fiscale")]//strong'),
            dayfirst=True,
            default=NotAvailable
        )(self.doc)


class TncPage(HTMLPage):
    @method
    class fill_account(ItemElement):
        def obj_id(self):
            return Attr('//span[text()="%s"]' % self.obj.label, 'data-account-label')(self)

        obj_number = CleanText('//h3[@class="c-product-title__sublabel"]')
        obj_type = Account.TYPE_REAL_ESTATE

    @method
    class iter_investment(TableElement):
        item_xpath = '//h3[text()="Mes investissements en cours"]/following::table[1]/tbody/tr'
        head_xpath = '//h3[text()="Mes investissements en cours"]/following::table[1]/thead/tr/th'

        col_label = 'Projet'
        col_valuation = 'Montant investi'
        col_diff = '+/- values latentes'

        class item(ItemElement):
            klass = Investment

            obj_label = Base(TableCell('label'), CleanText('.//span[@class="c-link__label "]'))
            obj_valuation = CleanDecimal.French(TableCell('valuation'))
            obj_diff = CleanDecimal.French(TableCell('diff'))
            obj_code = Base(TableCell('label'), CleanText('.//span[@class="c-table__mention"]'))


class ErrorPage(HTMLPage):
    def on_load(self):
        error = (
            Attr('//input[@required][@id="profile_lei_type_identifier"]', 'data-message', default=None)(self.doc)
            or CleanText('//h2[@class="page-title"][contains(text(), "Actualisation")]', default=None)(self.doc)
        )
        if error:
            raise ActionNeeded(error)

    def get_error_message(self):
        return Coalesce(
            CleanText('//h2[contains(@class, "title--error")]', transliterate=True),
            CleanText('//form[@name="blockingPagesType"]/p[2]', transliterate=True),
            CleanText('//form[@name="blockingPagesType"]/p'),
            CleanText('//form[@name="documents_request"]//p/span'),
            default=NotAvailable,
        )(self.doc)


class MinorPage(HTMLPage):
    def get_error_message(self):
        return CleanText('//div[@id="modal-main-content"]//p')(self.doc)


class ExpertPage(LoggedPage, HTMLPage):
    pass


def MyInput(*args, **kwargs):
    args = ('//input[contains(@name, "%s")]' % args[0], 'value',)
    kwargs.update(default=NotAvailable)
    return Attr(*args, **kwargs)


def MySelect(*args, **kwargs):
    args = ('//select[contains(@name, "%s")]/option[@selected]' % args[0],)
    kwargs.update(default=NotAvailable)
    return CleanText(*args, **kwargs)


class ProfilePage(LoggedPage, HTMLPage):

    def get_children_firstnames(self):
        names = []

        for child in self.doc.xpath('//span[@class="transfer__account-name"]'):
            name = child.text.split('\n')
            assert len(name) > 1, "There is a child without firstname or the html code has changed !"
            names.append(child.text.split('\n')[0])

        return names

    @method
    class get_profile(ItemElement):
        klass = Person

        obj_name = Format('%s %s %s', MySelect('genderTitle'), MyInput('firstName'), MyInput('lastName'))
        obj_firstname = MyInput('firstName')
        obj_lastname = MyInput('lastName')
        obj_nationality = CleanText('//span[contains(text(), "Nationalité")]/span')
        obj_spouse_name = MyInput('spouseFirstName')
        obj_children = CleanDecimal(MyInput('dependentChildren'), default=NotAvailable)
        obj_family_situation = MySelect('maritalStatus')
        obj_matrimonial = MySelect('matrimonial')
        obj_housing_status = MySelect('housingSituation')
        obj_job = MyInput('occupation')
        obj_job_start_date = Date(MyInput('employeeSince'), default=NotAvailable)
        obj_company_name = MyInput('employer')
        obj_socioprofessional_category = MySelect('socioProfessionalCategory')


class CardInformationPage(LoggedPage, HTMLPage):
    def get_card_number(self, card):
        """
        Cards seems to be related to 2 hashes. The first one is already set in the account`key` (card._key)
        the second one is only findable in this page (which gives us the card number).
        We need to find the link between both hash to set the card number to the good account.
        """
        # card_key it's not always used/present on this page.
        # we can get the identifier associated with the card based on the label
        # label --> card_key --> card_number
        ultim_card_label = re.sub(r'PREMIER|CLASSIC', 'ULTIM', card.label)
        metal_card_label = re.sub(r'PREMIER|CLASSIC', 'METAL', card.label)
        # Boursorama replaced "PREMIER" and "CLASSIC" cards for "ULTIM" or "METAL"
        # cards but there are still occurrences of old names "PREMIER" or "CLASSIC"
        # in some of the HTML in which we fetch the card label
        card_key = Regexp(
            Coalesce(
                Attr(f'//h3[contains(normalize-space(text()), "{card.label}")]', "id", default=NotAvailable),
                Attr(f'//h3[contains(normalize-space(text()), "{ultim_card_label}")]', "id", default=NotAvailable),
                Attr(f'//h3[contains(normalize-space(text()), "{metal_card_label}")]', "id", default=NotAvailable),
                default=NotAvailable,
            ),
            'credit-card-title-(.*)',
            default=NotAvailable,
        )(self.doc)

        if card_key:
            card_number = Regexp(
                CleanText(f'//div[@data-card-key="{card_key}"]'),
                r'(\d{4} ?\*{4} ?\*{4} ?\d{4})',
                default=NotAvailable,
            )(self.doc)
            if card_number:
                # 1234 **** **** 1234
                return card_number.replace(' ', '')

        # We get the card number associate to the card key
        card_number = Regexp(
            CleanText(f'//option[@value="{card._key}"]'),
            r'(\d{4}\*{8}\d{4})|^\d{4}\*{8}\d{4}$',
            default=NotAvailable
        )(self.doc)

        # There is only one place in the code where we can associate both hash to each other. The second hash
        # that we found with the first one match with a card account key.
        url = Link('//a[contains(@href, "%s/calendrier")]' % card._key, NotAvailable)(self.doc)

        # If there is no coming, that's not a deferred card
        if not empty(url):
            return card_number


class HomePage(LoggedPage, HTMLPage):
    pass


class NoTransferPage(LoggedPage, HTMLPage):
    pass


class TransferMainPage(LoggedPage, HTMLPage):
    pass


class TransferAccounts(LoggedPage, HTMLPage):
    def on_load(self):
        super(TransferAccounts, self).on_load()
        self.logger.warning('CANARY Boursorama: Usage detected of an old interface transfer web page')

    @method
    class iter_accounts(ListElement):
        item_xpath = '//a[has-class("next-step")][@data-value]'

        class item(ItemElement):
            klass = Account

            obj_id = CleanText('.//div[@class="transfer__account-number"]')
            obj__sender_id = Attr('.', 'data-value')

    def submit_account(self, id):
        for account in self.iter_accounts():
            if account.id == id:
                break
        else:
            raise AccountNotFound()

        form = self.get_form(name='DebitAccount')
        form['DebitAccount[debit]'] = account._sender_id
        form.submit()

    @method
    class iter_emitters(ListElement):
        item_xpath = '//ul[@class="o-grid"]/li[@class="o-grid__item"]'

        class item(ItemElement):
            klass = Emitter

            obj_id = CleanText('.//div[contains(@class, "c-card-ghost__sub-label")]')
            obj_label = CleanText('.//div[contains(@class, "c-card-ghost__top-label")]')
            obj_currency = CleanCurrency('.//span[contains(@class, "c-card-ghost__side-panel")]')
            obj_balance = CleanDecimal.French('.//span[contains(@class, "c-card-ghost__side-panel")]')
            obj__bourso_id = Attr('.//div[has-class("c-card-ghost")]', 'data-value')


class TransferRecipients(LoggedPage, HTMLPage):
    @method
    class iter_recipients(ListElement):
        item_xpath = '//div[contains(@class, "deploy__wrapper")]//label'

        class item(ItemElement):
            klass = Recipient

            def condition(self):
                iban = Field('iban')(self)
                if iban:
                    return is_iban_valid(iban)
                # some internal accounts don't show iban
                return True

            obj_id = CleanText('.//div[@class="c-card-ghost__sub-label"]')
            obj_bank_name = Regexp(
                CleanText('.//div[@class="transfer__account-name"]'), pattern=r'- ([^-]*)$',
                default=NotAvailable
            )

            def obj_label(self):
                label = Regexp(
                    CleanText('.//div[@class="c-card-ghost__top-label"]'),
                    pattern=r'^(.*?)(?: -[^-]*)?$'
                )(self)
                return label.rstrip('-').rstrip()

            def obj_category(self):
                text = CleanText('./ancestor::div[has-class("deploy--item")]//span')(self).lower()
                if 'mes comptes boursorama banque' in text:
                    return 'Interne'
                elif any(exp in text for exp in ('comptes externes', 'comptes de tiers', 'mes bénéficiaires')):
                    return 'Externe'

            def obj_iban(self):
                if Field('category')(self) == 'Externe':
                    return Field('id')(self)

            def obj_enabled_at(self):
                return datetime.datetime.now().replace(microsecond=0)

            obj__tempid = Attr('./input', 'value')

    def submit_recipient(self, tempid):
        form = self.get_form(name='CreditAccount')
        form['CreditAccount[creditAccountKey]'] = tempid
        form.submit()

    def is_new_recipient_allowed(self):
        return True


class RecipientsPage(LoggedPage, HTMLPage):
    @method
    class iter_recipients(ListElement):
        item_xpath = '//li[@class="c-link-list-collapsable__item"]'

        obj_id = ''
        obj_label = CleanText(
            '//span[@class="o-list-inline__item '
            + 'c-link-list-collapsable__label"]',
        )
        obj_bank_name = CleanText(Regexp(Field('_sublabel'), '(.+)·'))
        obj_category = 'Externe'

        def obj_iban(self):
            _, _, iban = Field('sublabel')(self).rpartition('·')
            return clean_iban(iban.lstrip())

        def obj_enabled_at(self):
            return datetime.datetime.now().replace(microsecond=0)

        obj__sublabel = CleanText(
            '//span[@class="o-list-inline__item '
            + 'c-link-list-collapsable__sub-label"]',
        )


class NewTransferWizard(LoggedPage, HTMLPage):
    def get_errors(self):
        return CleanText('//form//div[@class="form-errors"]//li')(self.doc)

    # STEP 1 - Select account
    def submit_account(self, account_id):
        no_account_msg = CleanText('//div[contains(@class, "alert--warning")]')(self.doc)
        if 'Vous ne possédez pas de compte éligible au virement' in no_account_msg:
            raise AccountNotFound()
        elif no_account_msg:
            raise AssertionError('Unhandled error message when trying to select an account for a new transfer: "%s"'
                                 % no_account_msg)

        form = self.get_form()
        debit_account = CleanText(
            '//input[./following-sibling::div/span/span[contains(text(), "%s")]]/@value' % account_id
        )(self.doc)
        if not debit_account:
            raise AccountNotFound()

        form['DebitAccount[debit]'] = debit_account
        form.submit()

    @method
    class iter_emitters(ListElement):
        item_xpath = '//ul[has-class("c-info-box")]/li[has-class("c-info-box__item")]'

        class item(ItemElement):
            klass = Emitter

            obj_id = CleanText('.//span[@class="c-info-box__account-sub-label"]/span')
            obj_label = CleanText('.//span[@class="c-info-box__account-label"]')
            obj_currency = CleanCurrency(
                './/span[has-class("c-info-box__account-balance")]',
                default=NotAvailable,
            )
            obj_balance = CleanDecimal.French(
                './/span[has-class("c-info-box__account-balance")]',
                default=NotAvailable,
            )
            obj__bourso_id = Attr('.//div[has-class("c-info-box__content")]', 'data-value')

    # STEP 2 - Select recipient (or to create a new recipient)
    @method
    class iter_recipients(ListElement):
        item_xpath = '//div[contains(@id, "panel-")]//div[contains(@class, "panel__body")]//label'

        class item(ItemElement):
            klass = Recipient

            obj_id = CleanText(
                './/span[contains(@class, "account-sub-label")]/span[not(contains(@class,"account-before-sub-label"))]',
                replace=[(' ', '')],
            )

            # bank name finish with the following text " •"
            obj_bank_name = CleanText('.//span[contains(@class, "account-before-sub-label")]', symbols=['•'])

            def obj_label(self):
                bank_name = Field('bank_name')(self)
                label = CleanText('.//span[contains(@class, "account-label")]')(self)

                # Sometimes, Boursorama appends the bank name at the end of the label
                if not empty(bank_name):
                    label = label.replace('- %s' % bank_name, '').strip()

                # There is an exceptional case where the recipient has an empty label.
                # In such a case, at least use the name of the bank
                if label == '':
                    label = bank_name
                return label

            def obj_category(self):
                text = CleanText(
                    './ancestor::div[contains(@class, "panel__body")]'
                    + '/preceding-sibling::div[contains(@class, "panel__header")]'
                    + '//span[contains(@class, "panel__title")]'
                )(self).lower()
                if 'mes comptes boursorama banque' in text:
                    return 'Interne'
                elif any(exp in text for exp in ('comptes externes', 'comptes de tiers', 'mes bénéficiaires')):
                    return 'Externe'

            def obj_iban(self):
                if Field('category')(self) == 'Externe':
                    # Sometimes, there are lower case letters in the middle
                    # of the IBAN. But IBAN needs to be all upper case.
                    return Upper(Field('id'))(self)
                return NotAvailable

            def obj_enabled_at(self):
                return datetime.datetime.now().replace(microsecond=0)

            obj__tempid = Attr('./input', 'value')

    def submit_recipient(self, tempid):
        form = self.get_form(name='CreditAccount')

        # newBeneficiary should only be filled when operation might be allowed
        # So it should not be filled for Livret accounts for example.'
        if HasElement('//input[@id="CreditAccount_newBeneficiary"]')(self.doc):
            # newBeneficiary values:
            # 0 = Existing recipient; 1 = New recipient
            form['CreditAccount[newBeneficiary]'] = 0

        form['CreditAccount[credit]'] = tempid

        form.submit()

    def is_new_recipient_allowed(self):
        try:
            self.get_form(name='CreditAccount')
        except FormNotFound:
            return False
        return HasElement('//input[@id="CreditAccount_newBeneficiary"]')(self.doc)

    # STEP 3 -
    # If using existing recipient: select the amount
    # If new beneficiary: select if new recipient is own account or third party one
    # For the moment, we only support the transfer to an existing recipient
    def submit_amount(self, amount):
        error_msg = self.get_errors()
        if error_msg:
            raise TransferBankError(message=error_msg)

        form = self.get_form(name='Amount')
        str_amount = str(amount.quantize(Decimal('0.00'))).replace('.', ',')
        form['Amount[amount]'] = str_amount
        form.submit()

    # In case the amount form has an error, we want to be able to detect it.
    def get_amount_error(self):
        return CleanText(
            '//form[@name="Amount"]//*[@id="Amount_amount-error"]',
            default='',
        )(self.doc)

    # STEP 4 - SKIPPED - Fill new beneficiary info

    # STEP 5 - SKIPPED - select the amount after new beneficiary

    # STEP 6 for "programme" - To select deferred or periodic
    def submit_programme_date_type(self, transfer_date_type):
        error_msg = self.get_errors()
        if error_msg:
            raise TransferBankError(message=error_msg)

        assert transfer_date_type == TransferDateType.DEFERRED, "periodic transfer not supported"

        form = self.get_form(name='Scheduling')
        # SchedulingType: 2=Deffered ; 3=Periodic
        form['Scheduling[schedulingType]'] = '2'
        form.submit()

    # STEP 6 for "immediate" - Enter label and scheduling type
    # STEP 7 for "programme" - Enter label and scheduled date
    def submit_info(self, label, transfer_date_type, exec_date=None):
        error_msg = self.get_errors()
        if error_msg:
            raise TransferBankError(message=error_msg)

        form = self.get_form(name='Characteristics')

        form['Characteristics[label]'] = label
        if transfer_date_type == TransferDateType.INSTANT:
            form['Characteristics[schedulingType]'] = '1'
        elif transfer_date_type == TransferDateType.FIRST_OPEN_DAY:
            # It looks like that no schedulingType is sent in the "Ponctual"
            # ie FIRST_OPEN_DAY case
            form['Characteristics[schedulingType]'] = None
        elif transfer_date_type == TransferDateType.DEFERRED:
            if empty(exec_date):
                exec_date = datetime.date.today()
            form['Characteristics[scheduledDate]'] = exec_date.strftime('%d/%m/%Y')
        else:
            raise AssertionError("Periodic transfer is not supported")

        form.submit()


class NewTransferEstimateFees(LoggedPage, HTMLPage):
    # STEP 7 for "immediate"
    # STEP 8 for "programme"
    is_here = '//h3[text()="Estimation des frais liés à l\'instrument"]'

    XPATH_AMOUNT = '//form[@name="EstimatedFees"]//tr[has-class("definition-list__row")][th[contains(text(),"Frais prélevés")]]/td[1]'

    def get_errors(self):
        return CleanText('//form//div[@class="form-errors"]//li')(self.doc)

    def get_transfer_fee(self):
        return CleanDecimal.French(self.XPATH_AMOUNT)(self.doc)

    def submit(self):
        error_msg = self.get_errors()
        if error_msg:
            raise TransferBankError(message=error_msg)

        form = self.get_form(name='EstimatedFees')
        form.submit()


class NewTransferUnexpectedStep(LoggedPage, HTMLPage):
    # STEP 7 for "immediate" if not "estimation des frais" and a form error
    # STEP 8 for "programme" if not "estimation des frais" and a form error
    def is_here(self):
        # If we are not on the "estimation des frais" page
        return not bool(
            self.doc.xpath(
                '//h3[text()="Estimation des frais liés à l\'instrument" or text()="Confirmer votre virement"]'
            )
        )

    def get_errors(self):
        return CleanText('//form//div[@class="form-errors"]//li')(self.doc)


class TransferOtpPage(LoggedPage, HTMLPage):
    def _is_form(self, **kwargs):
        try:
            self.get_form(**kwargs)
        except FormNotFound:
            return False
        return True

    def _get_sca_payload(self):
        return Attr(
            '//form[@data-strong-authentication-form]/div[@data-strong-authentication-payload]',
            'data-strong-authentication-payload'
        )(self.doc)

    def _get_main_challenge_type(self):
        otp_data = json.loads(self._get_sca_payload())
        otp_main_challenge = otp_data['challenges'][0]
        return otp_main_challenge['type']

    def is_send_sms(self):
        return (
            self._is_form(xpath='//form[@data-strong-authentication-form]')
            and self._get_main_challenge_type() == 'brs-otp-sms'
        )

    def is_send_email(self):
        return (
            self._is_form(xpath='//form[@data-strong-authentication-form]')
            and self._get_main_challenge_type() == 'brs-otp-email'
        )

    def is_send_app(self):
        return (
            self._is_form(xpath='//form[@data-strong-authentication-form]')
            and self._get_main_challenge_type() == 'brs-otp-webtoapp'
        )

    def get_api_config(self):
        raw_json = Regexp(
            CleanText('//script[contains(text(), "BRS_CONFIG = {")]'),
            r'BRS_CONFIG = ({.+?});',
        )(self.doc)
        raw_config = json.loads(raw_json)

        return {
            'baseurl': 'https://%s%s' % (
                raw_config['API_HOST'],
                raw_config['API_PATH'],
            ),
            'user_hash': raw_config['USER_HASH'],
        }

    def _get_otp_data(self, action):
        api_config = self.get_api_config()
        otp_data = {}

        otp_json_data = json.loads(self._get_sca_payload())
        # TODO: Check the path for the SMS OTP.
        # breakpoint()
        challenge_data = otp_json_data['challenges'][0]['parameters']
        challenge_data = challenge_data['formScreen']['actions']
        try:
            challenge_data = challenge_data[action]
        except KeyError:
            # No actual action with that name, e.g. no 'start' for app
            # validation, so we want to just skip the current step.
            return None

        challenge_data = challenge_data['api']

        otp_url = challenge_data['href']
        otp_url = otp_url.replace('{userHash}', api_config['user_hash'])

        resource_id = challenge_data['params'].pop('resourceId', None)
        if resource_id:
            otp_url = otp_url.replace('{resourceId}', resource_id)

        otp_data['url'] = '%s%s' % (api_config['baseurl'], otp_url)

        # Note that we have removed 'resourceId' from the parameters here
        # beforehand, so it will be excluded here.
        for key, value in challenge_data['params'].items():
            otp_data[key] = value

        return otp_data

    def send_otp(self):
        otp_data = self._get_otp_data('start')
        if otp_data is None:
            return False

        url = otp_data.pop('url')
        self.browser.location(url, data=otp_data)
        return True

    def get_confirm_otp_data(self):
        # The "confirm otp data" is the data required to validate
        # the OTP code the user will give us.
        otp_data = self._get_otp_data('check')
        if otp_data is None:
            raise AssertionError('Could not find OTP confirmation data.')

        return otp_data

    def get_confirm_otp_form(self):
        # The "confirm otp form" is the html form used to go to
        # the next step (page) after the otp data has been validated.
        otp_form = self.get_form(xpath='//form[@data-strong-authentication-form]')
        otp_form = {k: v for k, v in dict(otp_form).items()}
        otp_form['url'] = self.url
        return otp_form


class NewTransferConfirm(LoggedPage, HTMLPage):
    # STEP 7 for "immediate" - Confirmation page
    # STEP 8 for "programme"
    # STEP 8 for "immediate" if page "estimation des frais" before
    # STEP 9 for "programme" if page "estimation des frais" before
    is_here = '//h3[text()="Confirmer votre virement"]'

    def get_errors(self):
        return CleanText('//form//div[@class="form-errors"]//li')(self.doc)

    @method
    class get_transfer(ItemElement):
        klass = Transfer

        XPATH_TMPL = '//form[@name="Confirm"]//tr[has-class("definition-list__row")][th[contains(text(),"%s")]]/td[1]/span[1]'

        mapping_date_type = {
            'Ponctuel': TransferDateType.FIRST_OPEN_DAY,
            'Classique (1 à 3 jours ouvrés)': TransferDateType.FIRST_OPEN_DAY,
            'Instantané': TransferDateType.INSTANT,
            'Différé': TransferDateType.DEFERRED,
            'Permanent': TransferDateType.PERIODIC,
        }

        obj_account_label = CleanText(XPATH_TMPL % 'Compte à débiter')
        obj_recipient_label = CleanText(XPATH_TMPL % 'Compte à créditer')
        obj_amount = CleanDecimal.French(XPATH_TMPL % 'Montant en euro')
        obj_currency = CleanCurrency(XPATH_TMPL % 'Montant en euro')
        obj_label = CleanText(XPATH_TMPL % 'Motif visible par le bénéficiaire')
        obj_date_type = Map(
            CleanText(XPATH_TMPL % 'Type de virement'),
            mapping_date_type,
        )

        def obj_exec_date(self):
            type_ = Field('date_type')(self)
            if type_ in [TransferDateType.INSTANT, TransferDateType.FIRST_OPEN_DAY]:
                return datetime.date.today()
            elif type_ == TransferDateType.DEFERRED:
                return Date(
                    CleanText(self.XPATH_TMPL % "Date d'envoi"),
                    parse_func=parse_french_date,
                )(self)

    def submit(self):
        error_msg = self.get_errors()
        if error_msg:
            raise TransferBankError(message=error_msg)

        form = self.get_form(name='Confirm')
        form.submit()


class NewTransferSent(TransferOtpPage):
    # STEP 9 for immediat - Confirmation de virement.
    # STEP 10 for "programme"
    def get_errors(self):
        message = Coalesce(
            CleanText('//div[has-class("alert--danger")]'),
            CleanText('//div[@class="form-errors"]//li'),
            CleanText('//div[has-class("c-alert--error")]/div[has-class("c-alert__text")]'),
            default=''
        )(self.doc)

        # This is for the 3rd Coalesce option, the message contains (without any newline):
        # Des questions relatives à ce virement?
        # Consultez l'aide en ligne ou contactez le service client au (+33)1 46 09 39 48.
        #
        # Which might be misleading for the end user.
        message = re.sub(r'Des questions relatives à ce virement\? Consultez.*', '', message).strip()
        return message

    def is_confirmed(self):
        return CleanText('//h3[text()="Confirmation"]')(self.doc) != ""

    def get_alert_message(self):
        return CleanText(
            '//*[contains(@class, "c-alert__text")]',
            default='',
        )(self.doc)


class TransferCharacteristics(LoggedPage, HTMLPage):
    def get_option(self, select, text):
        for opt in select.xpath('option'):
            if opt.text_content() == text:
                return opt.attrib['value']

    def submit_info(self, amount, label, exec_date):
        form = self.get_form(name='Characteristics')

        assert amount > 0
        amount = str(amount.quantize(Decimal('0.00'))).replace('.', ',')
        form['Characteristics[amount]'] = amount
        form['Characteristics[label]'] = label

        if not exec_date:
            exec_date = datetime.date.today()
        if datetime.date.today() == exec_date:
            assert self.get_option(form.el.xpath('//select[@id="Characteristics_schedulingType"]')[0], 'Ponctuel') == '1'
            form['Characteristics[schedulingType]'] = '1'
        else:
            assert self.get_option(form.el.xpath('//select[@id="Characteristics_schedulingType"]')[0], 'Différé') == '2'
            form['Characteristics[schedulingType]'] = '2'
            form['Characteristics[scheduledDate]'] = exec_date.strftime('%d/%m/%Y')

        form['Characteristics[notice]'] = 'none'
        form.submit()


class TransferConfirm(LoggedPage, HTMLPage):
    def on_load(self):
        errors = CleanText('//li[contains(text(), "Le montant du virement est inférieur au minimum")]')(self.doc)
        if errors:
            raise TransferInvalidAmount(message=errors)

    def need_refresh(self):
        return not self.doc.xpath('//form[@name="Confirm"]//button[contains(text(), "Valider")]')

    @method
    class get_transfer(ItemElement):
        klass = Transfer

        obj_label = CleanText('//span[@id="transfer-label"]/span[@class="transfer__account-value"]')
        obj_amount = CleanDecimal.French('//span[@id="transfer-amount"]/span[@class="transfer__account-value"]')
        obj_currency = CleanCurrency('//span[@id="transfer-amount"]/span[@class="transfer__account-value"]')

        obj_account_label = CleanText('//span[@id="transfer-origin-account"]')
        obj_recipient_label = CleanText('//span[@id="transfer-destination-account"]')

        def obj_exec_date(self):
            type_ = CleanText('//span[@id="transfer-type"]/span[@class="transfer__account-value"]')(self)
            if type_ == 'Ponctuel':
                return datetime.date.today()
            elif type_ == 'Différé':
                return Date(
                    CleanText('//span[@id="transfer-date"]/span[@class="transfer__account-value"]'),
                    dayfirst=True
                )(self)

    def submit(self):
        form = self.get_form(name='Confirm')
        form.submit()


class TransferSent(TransferOtpPage):
    def get_errors(self):
        return CleanText('//form[@name="Confirm"]/div[@class="form-errors"]//li')(self.doc)

    def is_confirmed(self):
        return CleanText('//h3[text()="Confirmation"]')(self.doc) != ""


class AddRecipientPage(TransferOtpPage):
    def on_load(self):
        super(AddRecipientPage, self).on_load()

        err = CleanText('//div[@class="form-errors"]', default=None)(self.doc)
        if err:
            raise AddRecipientBankError(message=err)

        # Sometimes we have the following alert:
        #
        #   Votre connexion à l'Espace Client ne présente pas les
        #   caractéristiques habituelles. Nous vous invitons à renouveler
        #   l'opération dans un délai de 72h ou depuis une adresse (IP) de
        #   connexion déjà connue par Boursorama Banque. Pour plus
        #   d'informations, rendez-vous sur notre aide en ligne, rubrique
        #   sécurité informatique : https://bour.so/faq/9424002
        #
        # This occurs when using the main website at clients.boursorama.com
        # with a different IP from the one previously used. This also occurs
        # when an actor with such an IP tries accessing accounts through
        # clients.boursorama.com or other domains after such a case has
        # occurred.
        #
        # We need to detect it to raise a ScrapingBlocked in this case.
        alert = CleanText(
            '//div[contains(@class, "c-alert__text")]',
            default=None,
        )(self.doc)

        if alert:
            if (
                re.search(r'caract.ristiques habituelles', alert)
                and re.search(r'dans un d.lai de 72h', alert)
            ):
                raise ScrapingBlocked()

            if 'cet iban est déjà présent' in alert.casefold():
                raise AddRecipientBankError(message=alert)

            raise AssertionError(f'Unhandled alert: {alert}')

    def is_type_choice(self):
        return self._is_form(name='choiceAccountType')

    def submit_choice_external_type(self):
        form = self.get_form(name='choiceAccountType')
        form['choiceAccountType[type]'] = 'tiers'
        form.submit()

    def is_characteristics(self):
        return self._is_form(name='externalAccountsPrepareType')

    def submit_recipient(self, recipient):
        form = self.get_form(name='externalAccountsPrepareType')

        try:
            country_code = BENEFICIARY_COUNTRY_CODES[recipient.iban[:2]]
        except KeyError:
            raise AssertionError(f'Unhandled country code: {country_code}')

        form['externalAccountsPrepareType[countryCode]'] = country_code
        form['externalAccountsPrepareType[type]'] = 'tiers'
        form['externalAccountsPrepareType[label]'] = recipient.label
        form['externalAccountsPrepareType[beneficiaryIdentity]'] = recipient.label
        form['externalAccountsPrepareType[iban]'] = recipient.iban
        form['submit'] = ''
        form.submit()

    def is_confirm_send_sms(self):
        return self._is_form(name='externalAccountsConfirmType')

    def confirm_send_sms(self):
        form = self.get_form(name='externalAccountsConfirmType')
        form.submit()

    def is_created(self):
        return CleanText('//p[contains(text(), "Le bénéficiaire a bien été ajouté.")]')(self.doc) != ""


class AddRecipientOtpSendPage(LoggedPage, JsonPage):
    def is_confirm_otp(self):
        return Dict('success')(self.doc)


class OtpCheckPage(LoggedPage, JsonPage):
    # Same url for Recipient add and 90d 2FA
    def is_success(self):
        return Dict('success', default=False)(self.doc)


class PEPPage(LoggedPage, HTMLPage):
    pass


class CurrencyListPage(HTMLPage):
    @method
    class iter_currencies(ListElement):
        item_xpath = '//select[@class="c-select currency-change"]/option'

        class item(ItemElement):
            klass = Currency

            obj_id = Attr('./.', 'value')

    def get_currency_list(self):
        CurIDList = []
        for currency in self.iter_currencies():
            currency.id = currency.id[0:3]
            if currency.id not in CurIDList:
                CurIDList.append(currency.id)
                yield currency


class CurrencyConvertPage(JsonPage):
    def get_rate(self):
        if 'error' not in self.doc:
            return Decimal(str(self.doc['rate']))


class AccountsErrorPage(LoggedPage, HTMLPage):
    def is_here(self):
        # some braindead error seems to affect many accounts until we retry
        return '[E10008]' in CleanText('//div')(self.doc)

    def on_load(self):
        raise BrowserUnavailable()


class IncidentTradingPage(HTMLPage):
    def get_error_message(self):
        return CleanText('//p[contains(text(), "incident")]')(self.doc)
