# -*- coding: utf-8 -*-
# Copyright(C) 2010-2011  Romain Bignon, Pierre Mazière
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
import base64
import math
import random
from decimal import Decimal
from io import BytesIO
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs, urljoin

from dateutil.relativedelta import relativedelta
import requests

from woob.capabilities.base import empty, find_object, NotAvailable
from woob.capabilities.bank import (
    Account, Recipient, TransferError, TransferBankError, Transfer,
    AccountOwnership, Loan,
)
from woob.capabilities.bank.wealth import Investment, MarketOrder, MarketOrderDirection, MarketOrderType
from woob.capabilities.bill import Document, Subscription, DocumentTypes
from woob.capabilities.profile import Person, ProfileMissing
from woob.capabilities.contact import Advisor
from woob.browser.elements import method, ListElement, TableElement, ItemElement, DictElement
from woob.browser.exceptions import ServerError
from woob.browser.pages import LoggedPage, HTMLPage, JsonPage, FormNotFound, pagination, PartialHTMLPage
from woob.browser.filters.html import Attr, Link, TableCell, AttributeNotFound, AbsoluteLink
from woob.browser.filters.standard import (
    CleanText, Field, Regexp, Format, Date, CleanDecimal, Map, AsyncLoad, Async, Env, Slugify,
    BrowserURL, Eval, Currency, Base, Coalesce, MapIn, Lower,
)
from woob.browser.filters.json import Dict
from woob.exceptions import BrowserUnavailable, BrowserIncorrectPassword, ActionNeeded, ParseError
from woob.tools.capabilities.bank.transactions import FrenchTransaction, parse_with_patterns
from woob.tools.captcha.virtkeyboard import MappedVirtKeyboard, VirtKeyboardError
from woob.tools.html import html2text
from woob.tools.date import parse_french_date
from woob.tools.capabilities.bank.investments import IsinCode, IsinType


def myXOR(value, seed):
    s = ''
    for i in range(len(value)):
        s += chr(seed ^ ord(value[i]))
    return s


class LCLBasePage(HTMLPage):
    def get_from_js(self, pattern, end, is_list=False):
        """
        find a pattern in any javascript text
        """
        value = None
        for script in self.doc.xpath('//script'):
            txt = script.text
            if txt is None:
                continue

            start = txt.find(pattern)
            if start < 0:
                continue

            while True:
                if value is None:
                    value = ''
                else:
                    value += ','
                value += txt[start + len(pattern):start + txt[start + len(pattern):].find(end) + len(pattern)]

                if not is_list:
                    break

                txt = txt[start + len(pattern) + txt[start + len(pattern):].find(end):]

                start = txt.find(pattern)
                if start < 0:
                    break
            return value


class LCLVirtKeyboard(MappedVirtKeyboard):
    symbols = {
        # part and pro respectively.
        '0': ('9da2724133f2221482013151735f033c', 'd2b8975feed0efcd4d52dd8afe9dc398'),
        '1': ('873ab0087447610841ae1332221be37b', 'ea0963181efefd6f55bf5a2dd3903f98'),
        '2': ('93ce6c330393ff5980949d7b6c800f77', '1e2e896f0d8c3a27aa0889552be9ea15'),
        '3': ('b2d70c69693784e1bf1f0973d81223c0', '1a18623ee5e670150ac7e64d73e456de'),
        '4': ('498c8f5d885611938f94f1c746c32978', '0942e607d85f2feada611f3fa1ac7c81'),
        '5': ('359bcd60a9b8565917a7bf34522052c3', '404f2ba3b1bdf80116dd1aa240f3596e'),
        '6': ('aba912172f21f78cd6da437cfc4cdbd0', '0d4f22e343a969381896df051a550d7f'),
        '7': ('f710190d6b947869879ec02d8e851dfa', 'c052d6d6545b92beaabc062942b9810e'),
        '8': ('b42cc25e1539a15f767aa7a641f3bfec', 'd86f275c5558ed0ff85415a1dfd18ea9'),
        '9': ('cc60e5894a9d8e12ee0c2c104c1d5490', '1ddec5de5ad56809bce040e5afe847b7'),
    }

    url = "/outil/UAUT/Clavier/creationClavier?random="

    color = (255, 255, 255, 255)

    def __init__(self, basepage):
        img = basepage.doc.find("//img[@id='idImageClavier']")
        random.seed()
        self.url += "%s" % str(int(math.floor(int(random.random() * 1000000000000000000000))))
        super(LCLVirtKeyboard, self).__init__(
            BytesIO(basepage.browser.open(self.url).content),
            basepage.doc, img, self.color, "id")
        self.check_symbols(self.symbols, basepage.browser.responses_dirname)

    def get_symbol_code(self, md5sum):
        code = MappedVirtKeyboard.get_symbol_code(self, md5sum)
        return code[-2:]

    def get_string_code(self, string):
        code = ''
        for c in string:
            code += self.get_symbol_code(self.symbols[c])
        return code


class LoginPage(HTMLPage):
    def on_load(self):
        try:
            form = self.get_form(xpath='//form[@id="setInfosCGS" or @name="form"]')
        except FormNotFound:
            return

        form.submit()

    def login(self, login, passwd):
        try:
            vk = LCLVirtKeyboard(self)
        except VirtKeyboardError as err:
            self.logger.exception(err)
            return False

        password = vk.get_string_code(passwd)

        seed = -1
        s = "var aleatoire = "
        for script in self.doc.findall("//script"):
            if script.text is None or len(script.text) == 0:
                continue
            offset = script.text.find(s)
            if offset != -1:
                seed = int(script.text[offset + len(s) + 1:offset + len(s) + 2])
                break
        if seed == -1:
            raise ParseError("Variable 'aleatoire' not found")

        form = self.get_form('//form[@id="formAuthenticate"]')
        form['identifiant'] = login
        form['postClavierXor'] = base64.b64encode(
            myXOR(password, seed).encode("utf-8")
        )
        try:
            form['identifiantRouting'] = self.browser.IDENTIFIANT_ROUTING
        except AttributeError:
            pass

        form.submit(allow_redirects=False)

    def check_error(self):
        errors = self.doc.xpath(u'//*[@class="erreur" or @class="messError"]')
        if not errors or self.doc.xpath('//a[@href="/outil/UWHO/Accueil/"]'):
            return

        for error in errors:
            error_text = CleanText(error.xpath('./div/text()'))(self.doc)
            if 'Suite à la saisie de plusieurs identifiant / code erronés' in error_text:
                raise ActionNeeded(error_text)
            if 'Votre identifiant ou votre code personnel est incorrect' in error_text:
                raise BrowserIncorrectPassword(error_text)
        raise BrowserIncorrectPassword()


class ErrorPage(HTMLPage):
    def get_error_message(self):
        return CleanText('//div[@class="messError"]/div')(self.doc)


class RedirectPage(LoginPage, PartialHTMLPage):
    def is_here(self):
        # During login a form submit with an allow_redirects=False is done
        # The submit request can be done on contract urls following by a redirection
        # So if we get a 302 this new class avoids misleading on_load
        return self.response.status_code == 302


class MaintenancePage(HTMLPage):
    def get_error_code(self):
        return Regexp(
            CleanText('//div[contains(text(), "CODE ERREUR : ")]'),
            r'CODE ERREUR : (.*)',
            default=None,
        )(self.doc)

    def get_message(self):
        return CleanText('//div[@id="indispo_texte"]')(self.doc)


class ContractsPage(LoginPage, PartialHTMLPage):
    def on_load(self):
        # after login, we are redirect in ContractsPage even if there is an error at login
        # I let the error check code here to simplify
        # a better solution will be to put error check on browser.py and error parsing in pages.py
        self.check_error()

        # To avoid skipping contract page the first time we see it,
        # and to be able to get the contracts list from it
        if self.browser.parsed_contracts:
            self.select_contract()

    def get_contracts_list(self):
        return self.doc.xpath('//input[@name="contratId"]/@value')

    def select_contract(self, id_contract=None):
        link = self.doc.xpath('//a[contains(text(), "Votre situation globale")]')
        if not id_contract and len(link):
            self.browser.location(link[0].attrib['href'])
        else:
            form = self.get_form(nr=0)
            if 'contratId' in form:
                if id_contract:
                    form['contratId'] = id_contract
                self.browser.current_contract = form['contratId']
            form.submit()


class ContractRedirectionPage(ContractsPage):
    def should_submit_redirect_form(self):
        return bool(self.doc.xpath('//body[contains(@onload, "envoyerJeton()")]/form'))

    def submit_redirect_form(self):
        form = self.get_form(id='form')
        form.submit()


class PasswordExpiredPage(LoggedPage, HTMLPage):
    def get_message(self):
        return CleanText('//form[@id="changementCodeForm"]//span[contains(., "nouveau code d’accès")]')(self.doc)


class ContractsChoicePage(ContractsPage):
    def on_load(self):
        self.check_error()
        if not self.logged and not self.browser.current_contract:
            self.select_contract()


class OwnedItemElement(ItemElement):
    def get_ownership(self, owner):
        if re.search(r'(m|mr|me|mme|mlle|mle|ml)\.? (.*)\bou (m|mr|me|mme|mlle|mle|ml)\b(.*)', owner, re.IGNORECASE):
            return AccountOwnership.CO_OWNER
        elif all(n in owner for n in self.env['name'].split()):
            return AccountOwnership.OWNER
        return AccountOwnership.ATTORNEY


class AccountsPage(LoggedPage, HTMLPage):
    def on_load(self):
        warn = self.doc.xpath('//div[@id="attTxt"]')
        if len(warn) > 0:
            raise BrowserIncorrectPassword(warn[0].text)

    def get_name(self):
        return CleanText('//li[@id="nomClient"]/p')(self.doc)

    @method
    class get_accounts_list(ListElement):

        # XXX Ugly Hack to replace account by second occurrence.
        # LCL pro website sometimes display the same account twice and only second link is valid to fetch transactions.
        def store(self, obj):
            assert obj.id
            if obj.id in self.objects:
                self.logger.warning('There are two objects with the same ID! %s' % obj.id)
            self.objects[obj.id] = obj
            return obj

        item_xpath = '//tr[contains(@onclick, "redirect")]'
        flush_at_end = True

        class account(OwnedItemElement):
            klass = Account

            def condition(self):
                return '/outil/UWLM/ListeMouvement' in self.el.attrib['onclick']

            def load_details(self):
                link_id = Field('_link_id')(self)
                if link_id:
                    account_url = urljoin(self.page.browser.BASEURL, link_id)
                    return self.page.browser.async_open(url=account_url)
                return NotAvailable

            NATURE2TYPE = {
                '001': Account.TYPE_SAVINGS,
                '004': Account.TYPE_CHECKING,
                '005': Account.TYPE_CHECKING,
                '006': Account.TYPE_CHECKING,
                '007': Account.TYPE_SAVINGS,
                '012': Account.TYPE_SAVINGS,
                '023': Account.TYPE_CHECKING,
                '036': Account.TYPE_SAVINGS,
                '046': Account.TYPE_SAVINGS,
                '047': Account.TYPE_SAVINGS,
                '049': Account.TYPE_SAVINGS,
                '058': Account.TYPE_CHECKING,
                '068': Account.TYPE_PEA,
                '069': Account.TYPE_SAVINGS,
            }

            obj__link_id = Format('%s&mode=190', Regexp(CleanText('./@onclick'), "'(.*)'"))
            obj__agence = Regexp(Field('_link_id'), r'.*agence=(\w+)')
            obj__compte = Regexp(Field('_link_id'), r'compte=(\w+)')
            obj_id = Format('%s%s', Field('_agence'), Field('_compte'))
            obj__transfer_id = Format('%s0000%s', Field('_agence'), Field('_compte'))
            obj_label = CleanText('.//div[@class="libelleCompte"]')
            obj_currency = FrenchTransaction.Currency('.//td[has-class("right")]')
            obj_type = Map(Regexp(Field('_link_id'), r'.*nature=(\w+)'), NATURE2TYPE, default=Account.TYPE_UNKNOWN)
            obj__market_link = None
            obj_number = Field('id')

            def get_async_page(self):
                try:
                    async_page = Async('details').loaded_page(self)
                except ServerError as e:
                    async_page = HTMLPage(self.page.browser, e.response)
                    msg = CleanText('//div[@id="attTxt"]')(async_page.doc)
                    if 'Suite à un incident, nous ne pouvons donner suite à votre demande' in msg:
                        # it always happens for some account, even with firefox
                        # there is nothing we can do
                        return
                    raise

                return async_page

            def obj_balance(self):
                balance = None
                if 'professionnels' in self.page.browser.url and Field('type')(self) == Account.TYPE_CHECKING:
                    # for pro accounts with comings, balance without comings must be fetched on details page
                    async_page = self.get_async_page()
                    if async_page:
                        balance = async_page.get_balance_without_comings_main()
                        # maybe the next get_balance can be removed
                        # sometimes it returns the sum of transactions for last x days (47 ?)
                        if empty(balance):
                            self.logger.info('GET_BALANCE_MAIN EMPTY')
                            balance = async_page.get_balance_without_comings()
                if not empty(balance):
                    return balance
                return CleanDecimal.French('.//td[has-class("right")]')(self)

            def obj_ownership(self):
                async_page = self.get_async_page()
                if not async_page:
                    return NotAvailable
                owner = CleanText('//h5[contains(text(), "Titulaire")]')(async_page.doc)
                return self.get_ownership(owner)

    def get_deferred_cards(self):
        trs = self.doc.xpath('//tr[contains(@onclick, "EncoursCB")]')
        links = []

        for tr in trs:
            parent_id = Regexp(CleanText('./@onclick'), r'.*AGENCE=(\w+).*COMPTE=(\w+).*CLE=(\w+)', r'\1\2\3')(tr)
            link = Regexp(CleanText('./@onclick'), "'(.*)'")(tr)
            links.append((parent_id, link))

        return links

    @method
    class get_advisor(ItemElement):
        klass = Advisor

        obj_name = CleanText('//div[@id="contacterMaBqMenu"]//p[@id="itemNomContactMaBq"]/span')
        obj_email = obj_mobile = obj_fax = NotAvailable
        obj_phone = Regexp(
            CleanText('//div[@id="contacterMaBqMenu"]//p[contains(text(), "Tel")]', replace=[(' ', '')]),
            r'([\s\d]+)',
            default=NotAvailable
        )
        obj_agency = CleanText('//div[@id="sousContentAgence"]//p[@class="itemSousTitreMenuMaBq"][1]')

        def obj_address(self):
            address = CleanText(
                '//div[@id="sousContentAgence"]//p[@class="itemSousTitreMenuMaBq"][2]',
                default=None
            )(self)
            city = CleanText(
                '//div[@id="sousContentAgence"]//p[@class="itemSousTitreMenuMaBq"][3]',
                default=None
            )(self)
            if not (address and city):
                return NotAvailable
            return "%s %s" % (address, city)


class LoansTableElement(TableElement):
    flush_at_end = True

    col_id = re.compile('Emprunteur')
    col_balance = ['Capital restant dû', re.compile('Sommes totales restant dues'), re.compile('Montant utilisé')]
    col_amount = ['Montant du prêt', 'Montant maximum autorisé']
    col_maturity = ['Montant et date de la dernière échéance prélevée', 'Date de fin de prêt']
    col_next_payment = 'Montant et date de la prochaine échéance'

    class account(ItemElement):
        klass = Loan

        obj_balance = CleanDecimal.French(TableCell('balance'), sign='-')
        obj_currency = FrenchTransaction.Currency(TableCell('balance'))
        obj_type = Account.TYPE_LOAN
        obj_id = Env('id')
        obj__transfer_id = None
        obj__market_link = None
        obj_number = Regexp(CleanText(TableCell('id'), replace=[(' ', ''), ('-', '')]), r'(\d{11}[A-Z])')
        obj_name = Regexp(CleanText(TableCell('id')), r'(^\D+)', default=NotAvailable)
        obj_total_amount = CleanDecimal.French(TableCell('amount'))
        obj_account_label = Regexp(CleanText(TableCell('id')), r'- (.+)')
        obj_rate = CleanDecimal.French(
            Regexp(
                CleanText('.//div[@class="tooltipContent tooltipLeft testClic"]//ul/li[2]/node()[not(self::strong)]'),
                r'(.+)%',
                default=NotAvailable
            ),
            default=NotAvailable
        )
        obj_maturity_date = Date(
            Regexp(
                CleanText(TableCell('maturity', default='')),
                r'(\d{2}\/\d{2}\/\d{4})',
                default=''
            ),
            dayfirst=True,
            default=NotAvailable
        )
        obj_next_payment_amount = CleanDecimal.French(
            Regexp(
                CleanText(TableCell('next_payment', default='')),
                r'(^[\d ,]+) €',
                default=''
            ),
            default=NotAvailable
        )
        obj_next_payment_date = Date(
            Regexp(
                CleanText(TableCell('next_payment', default='')),
                r'(\d{2}\/\d{2}\/\d{4})',
                default=''
            ),
            dayfirst=True,
            default=NotAvailable
        )

        def obj_label(self):
            has_type = CleanText('./ancestor::table[.//th[contains(text(), "Type")]]', default=None)(self)
            if has_type:
                return CleanText('./td[2]')(self)
            else:
                return CleanText('./ancestor::table/preceding-sibling::div[1]')(self).split(' - ')[0]

        def obj_ownership(self):
            pattern = re.compile(
                r'(m|mr|me|mme|mlle|mle|ml)\.? (.*)\b(ou)? (m|mr|me|mme|mlle|mle|ml)\b(.*)',
                re.IGNORECASE
            )
            if pattern.search(CleanText(TableCell('id'))(self)):
                return AccountOwnership.CO_OWNER
            return AccountOwnership.OWNER

        def parse(self, el):
            label = Field('label')(self)
            trs = self.xpath(
                '//td[contains(text(), $label)]/ancestor::tr[1] | ./ancestor::table[1]/tbody/tr',
                label=label
            )
            i = [i for i in range(len(trs)) if el == trs[i]]
            if i:
                i = i[0]
            else:
                i = 0
            label = label.replace(' ', '')
            self.env['id'] = "%s%s%s" % (
                Regexp(CleanText(TableCell('id')), r'(\w+)\s-\s(\w+)', r'\1\2')(self),
                label.replace(' ', ''),
                i,
            )


class LoansPage(LoggedPage, HTMLPage):
    # Some connections have different types of Loans contained in different tables
    # with different table headers on the same LoansPage
    # By doing so, we can parse each type Loan table individually to retrieve the specific information we seek
    # without conflicts between table headers
    @method
    class iter_loans(ListElement):
        item_xpath = '//table[.//th[contains(text(), "Emprunteur")]]'

        class iter_loans_table(LoansTableElement):
            item_xpath = './tbody/tr[td[3]]'
            head_xpath = './thead/tr/th'


class LoansProPage(LoggedPage, HTMLPage):
    @method
    class get_list(TableElement):
        item_xpath = '//table[.//th[contains(text(), "Emprunteur")]]/tbody/tr[td[3]]'
        head_xpath = '//table[.//th[contains(text(), "Emprunteur")]]/thead/tr/th'
        flush_at_end = True

        col_id = re.compile('Emprunteur')
        col_balance = [u'Capital restant dû', re.compile('Sommes totales restant dues')]

        class account(ItemElement):
            klass = Loan

            obj_balance = CleanDecimal(TableCell('balance'), replace_dots=True, sign='-')
            obj_currency = FrenchTransaction.Currency(TableCell('balance'))
            obj_type = Account.TYPE_LOAN
            obj_id = Env('id')
            obj__transfer_id = None
            obj__market_link = None
            obj_number = Regexp(CleanText(TableCell('id'), replace=[(' ', ''), ('-', '')]), r'(\d{11}[A-Z])')

            def obj_label(self):
                has_type = CleanText('./ancestor::table[.//th[contains(text(), "Nature libell")]]', default=None)(self)
                if has_type:
                    return CleanText('./td[3]')(self)
                else:
                    return CleanText('./ancestor::table/preceding-sibling::div[1]')(self).split(' - ')[0]

            def parse(self, el):
                label = Field('label')(self)
                trs = self.xpath(
                    '//td[contains(text(), $label)]/ancestor::tr[1] | ./ancestor::table[1]/tbody/tr',
                    label=label
                )
                i = [i for i in range(len(trs)) if el == trs[i]]
                if i:
                    i = i[0]
                else:
                    i = 0
                label = label.replace(' ', '')
                self.env['id'] = "%s%s%s" % (
                    Regexp(CleanText(TableCell('id')), r'(\w+)\s-\s(\w+)', r'\1\2')(self),
                    label.replace(' ', ''),
                    i,
                )


class Transaction(FrenchTransaction):
    PATTERNS = [
        (
            re.compile(r'^(?P<category>CB) (?P<text>RETRAIT) DU (?P<dd>\d+)/(?P<mm>\d+)'),
            FrenchTransaction.TYPE_WITHDRAWAL,
        ),
        (re.compile(r'^(?P<category>(PRLV|PE)( SEPA)?) (?P<text>.*)'), FrenchTransaction.TYPE_ORDER),
        (re.compile(r'^(?P<category>CHQ\.) (?P<text>.*)'), FrenchTransaction.TYPE_CHECK),
        (re.compile(r'^(?P<category>RELEVE CB) AU (\d+)/(\d+)/(\d+)'), FrenchTransaction.TYPE_CARD),
        (
            re.compile(r'^(?P<category>CB) (?P<text>.*) (?P<dd>\d+)/(?P<mm>\d+)/(?P<yy>\d+)'),
            FrenchTransaction.TYPE_CARD,
        ),
        (re.compile(r'^(?P<category>(PRELEVEMENT|TELEREGLEMENT|TIP)) (?P<text>.*)'), FrenchTransaction.TYPE_ORDER),
        (re.compile(r'^(?P<category>(ECHEANCE\s*)?PRET)(?P<text>.*)'), FrenchTransaction.TYPE_LOAN_PAYMENT),
        (
            re.compile(
                r'^(TP-\d+-)?(?P<category>(EVI|VIR(EM(EN)?)?T?)(.PERMANENT)? ((RECU|FAVEUR) TIERS|SEPA RECU)?)( /FRM)?(?P<text>.*)'),
            FrenchTransaction.TYPE_TRANSFER,
        ),
        (re.compile(r'^(?P<category>REMBOURST)(?P<text>.*)'), FrenchTransaction.TYPE_PAYBACK),
        (re.compile(r'^(?P<category>COM(MISSIONS?)?)(?P<text>.*)'), FrenchTransaction.TYPE_BANK),
        (re.compile(r'^(?P<text>(?P<category>REMUNERATION).*)'), FrenchTransaction.TYPE_BANK),
        (re.compile(r'^(?P<text>(?P<category>ABON.*?)\s*.*)'), FrenchTransaction.TYPE_BANK),
        (re.compile(r'^(?P<text>(?P<category>RESULTAT .*?)\s*.*)'), FrenchTransaction.TYPE_BANK),
        (re.compile(r'^(?P<text>(?P<category>TRAIT\..*?)\s*.*)'), FrenchTransaction.TYPE_BANK),
        (re.compile(r'(?P<text>(?P<category>COTISATION).*)'), FrenchTransaction.TYPE_BANK),
        (re.compile(r'(?P<text>(?P<category>INTERETS).*)'), FrenchTransaction.TYPE_BANK),
        (re.compile(r'^(?P<category>REM CHQ) (?P<text>.*)'), FrenchTransaction.TYPE_DEPOSIT),
        (re.compile(r'^VIREMENT.*'), FrenchTransaction.TYPE_TRANSFER),
        (re.compile(r'.*(PRELEVEMENTS|PRELVT|TIP).*'), FrenchTransaction.TYPE_ORDER),
        (re.compile(r'.*CHEQUE.*'), FrenchTransaction.TYPE_CHECK),
        (re.compile(r'.*ESPECES.*'), FrenchTransaction.TYPE_DEPOSIT),
        (re.compile(r'.*(CARTE|CB).*'), FrenchTransaction.TYPE_CARD),
        (re.compile(r'.*(AGIOS|ANNULATIONS|IMPAYES|CREDIT).*'), FrenchTransaction.TYPE_BANK),
        (re.compile(r'.*(FRAIS DE TENUE DE COMPTE).*'), FrenchTransaction.TYPE_BANK),
        (re.compile(r'.*\b(RETRAIT)\b.*'), FrenchTransaction.TYPE_WITHDRAWAL),
    ]


class Pagination(object):
    def next_page(self):
        link = self.page.doc.xpath('//div[@class="pagination"]/a[span[contains(text(), "Page suivante")]]')

        if link:
            href = link[0].attrib.get('href')
            if href.startswith('javascript'):
                form = self.page.get_form(id="listeMouvementsForm")
                url_tuple = urlparse(self.page.url)

                query = re.match(r"javascript:listeMouvements(?:Pro|Par)\('([^']*)'\)", href)
                if not query:
                    raise AssertionError("Form of the javascript call to change pages has changed.")

                new_url = url_tuple._replace(query=query.group(1)).geturl()
                form.url = new_url
                return form.request
            return href


class AccountHistoryPage(LoggedPage, HTMLPage):
    class _get_operations(Pagination, Transaction.TransactionsElement):
        item_xpath = '//table[has-class("tagTab") and (not(@style) or @style="")]/tr'
        head_xpath = '//table[has-class("tagTab") and (not(@style) or @style="")]/tr/th'

        col_raw = [u'Vos opérations', u'Libellé']

        class item(Transaction.TransactionElement):
            def fill_env(self, page, parent=None):
                # This *Element's parent has only the dateguesser in its env,
                # and we want to use the same object, not copy it.
                self.env = parent.env

            def obj_rdate(self):
                rdate = self.obj.rdate
                date = Field('date')(self)

                if rdate > date:
                    date_guesser = Env('date_guesser')(self)
                    return date_guesser.guess_date(rdate.day, rdate.month)

                return rdate

            def obj__el(self):
                return self.el

            def condition(self):
                return (
                    self.parent.get_colnum('date') is not None
                    and len(self.el.findall('td')) >= 3
                    and self.el.get('class')
                    and 'tableTr' not in self.el.get('class')
                )

    def open_transaction_page(self, tr):
        # Those are summary for deferred card transactions,
        # they do not have details.
        if CleanText('./td[contains(text(), "RELEVE CB")]')(tr._el):
            return None

        row = Attr('.', 'id', default=None)(tr._el)
        assert row, 'HTML format of transactions details changed'

        if not re.match(r'\d+', row):
            return self.browser.open(
                Attr('.', 'href')(tr._el),
                method='POST',
            )
        try:
            return self.browser.open(
                '/outil/UWLM/ListeMouvementsParticulier/accesDetailsMouvement?element=%s' % row,
                method='POST',
            )
        except ServerError as e:
            # Sometimes this page can return a 502 with a message "Pour raison de maintenance informatique,
            # votre espace « gestion de comptes » est momentanément indisponible. Nous vous invitons à vous
            # reconnecter ultérieurement. Nous vous prions de bien vouloir nous excuser pour la gêne occasionnée."
            if e.response.status_code == 502:
                maintenance_page = MaintenancePage(self.browser, e.response)
                error_message = maintenance_page.get_message()
                if maintenance_page.get_error_code() == 'BPI-50':
                    raise BrowserUnavailable(error_message)
                raise AssertionError('An unexpected error occurred: %s' % error_message)
            raise

    def fix_transaction_stuff(self, obj, tr_page):
        raw = obj.raw
        if tr_page:
            # TODO move this xpath to the relevant page class
            raw = CleanText(
                '//td[contains(text(), "Libellé")]/following-sibling::*[1]|//td[contains(text(), "Nom du donneur")]/following-sibling::*[1]',
            )(tr_page.doc)

        if raw:
            if (
                obj.raw in raw
                or raw in obj.raw
                or ' ' not in obj.raw
            ):
                obj.raw = raw
                obj.label = raw
            else:
                obj.label = '%s %s' % (obj.raw, raw)
                obj.raw = '%s %s' % (obj.raw, raw)

            m = re.search(r'\d+,\d+COM (\d+,\d+)', raw)
            if m:
                obj.commission = -CleanDecimal(replace_dots=True).filter(m.group(1))

        elif not obj.raw:
            # Empty transaction label
            # TODO move this xpath to the relevant page class
            if tr_page:
                obj.raw = obj.label = CleanText(
                    """//td[contains(text(), "Nature de l'opération")]/following-sibling::*[1]"""
                )(tr_page.doc)

        if not obj.date:
            if tr_page:
                obj.date = Date(
                    CleanText(
                        """//td[contains(text(), "Date de l'opération")]/following-sibling::*[1]""",
                        default=''
                    ),
                    dayfirst=True,
                    default=NotAvailable
                )(tr_page.doc)

            obj.rdate = obj.date

            if tr_page:
                # TODO move this xpath to the relevant page class
                obj.vdate = Date(
                    CleanText(
                        '//td[contains(text(), "Date de valeur")]/following-sibling::*[1]',
                        default=''
                    ),
                    dayfirst=True,
                    default=NotAvailable
                )(tr_page.doc)

                # TODO move this xpath to the relevant page class
                obj.amount = CleanDecimal(
                    '//td[contains(text(), "Montant")]/following-sibling::*[1]',
                    replace_dots=True,
                    default=NotAvailable
                )(tr_page.doc)

        # ugly hack to fix broken html
        # sometimes transactions have really an amount of 0...
        if not obj.amount:
            if tr_page:
                # TODO move this xpath to the relevant page class
                obj.amount = CleanDecimal(
                    u'//td[contains(text(), "Montant")]/following-sibling::*[1]',
                    replace_dots=True,
                    default=NotAvailable
                )(tr_page.doc)

        obj.type = Transaction.TYPE_UNKNOWN
        if tr_page:
            typestring = CleanText(
                """//td[contains(text(), "Nature de l'opération")]/following-sibling::*[1]"""
            )(tr_page.doc)
            if typestring:
                for pattern, trtype in Transaction.PATTERNS:
                    match = pattern.match(typestring)
                    if match:
                        obj.type = trtype
                        break

        # Some transactions have no details, but we can find the type of the transaction,
        # the label and the category from the raw label.
        if obj.type == Transaction.TYPE_UNKNOWN:
            parse_with_patterns(obj.raw, obj, Transaction.PATTERNS)

        if obj.category == 'RELEVE CB':
            obj.type = Transaction.TYPE_CARD_SUMMARY

    @pagination
    def get_operations(self, date_guesser):
        return self._get_operations(self)(date_guesser=date_guesser)

    def get_balance_without_comings_main(self):
        return CleanDecimal.French(
            '//span[@class="mtSolde"]',
            default=NotAvailable
        )(self.doc)

    def get_balance_without_comings(self):
        return CleanDecimal.French(
            '//span[contains(text(), "Opérations effectuées")]//ancestor::div[1]/following-sibling::div',
            default=NotAvailable
        )(self.doc)


class CardsPage(LoggedPage, HTMLPage):
    def deferred_date(self):
        deferred_date = Regexp(
            CleanText('//div[@class="date"][contains(text(), "Carte")]'),
            r'le ([^:]+)',
            default=None
        )(self.doc)

        assert deferred_date, 'Cannot find deferred_date'
        return parse_french_date(deferred_date).date()

    def get_card_summary(self):
        amount = CleanDecimal.French('//div[@class="montantEncours"]')(self.doc)

        if amount:
            t = Transaction()
            t.date = t.rdate = self.deferred_date()
            t.type = Transaction.TYPE_CARD_SUMMARY
            t.label = t.raw = CleanText('//div[@class="date"][contains(text(), "Carte")]')(self.doc)
            t.amount = abs(amount)
            return t

    def format_url(self, url):
        cb_type = re.match(r'.*(UWCBEncours.*)/.*', url).group(1)
        return '/outil/UWCB/%s/listeOperations' % cb_type

    @method
    class iter_multi_cards(TableElement):
        head_xpath = '//table[@class="tagTab"]/tr/th'
        item_xpath = '//table[@class="tagTab"]//tr[position()>1]'

        col_label = re.compile('Type')
        col_number = re.compile('Numéro')
        col_owner = re.compile('Titulaire')
        col_coming = re.compile('Montant')

        class Item(ItemElement):
            klass = Account

            obj_type = Account.TYPE_CARD
            obj_balance = Decimal(0)
            obj_parent = Env('parent_account')
            obj_coming = CleanDecimal.French(TableCell('coming'))
            obj_currency = Currency(TableCell('coming'))
            obj__transfer_id = None
            obj__market_link = None

            obj__cards_list = CleanText(Env('cards_list'))

            def obj__transactions_link(self):
                link = Attr('.', 'onclick')(self)
                url = re.match('.*\'(.*)\'\\.*', link).group(1)
                return self.page.format_url(url)

            def obj_number(self):
                card_number = re.match('((XXXX ){3}X ([0-9]{3}))', CleanText(TableCell('number'))(self))
                return card_number.group(1)[0:16] + card_number.group(1)[-3:]

            def obj_label(self):
                return '%s %s %s' % (
                    CleanText(TableCell('label'))(self),
                    CleanText(TableCell('owner'))(self),
                    Field('number')(self),
                )

            def obj_id(self):
                card_number = re.match('((XXXX ){3}X([0-9]{3}))', CleanText(Field('number'))(self))
                return '%s-%s' % (Env('parent_account')(self).id, card_number.group(3))

    def get_single_card(self, parent_account):
        account = Account()

        card_info = CleanText('//select[@id="selectCard"]/option/text()')(self.doc)
        # ex: VISA INFINITE DD M FIRSTNAME LASTNAME N°XXXX XXXX XXXX X103
        regex = '(.*)N°((XXXX ){3}X([0-9]{3})).*'
        card_infos = re.match(regex, card_info)

        coming = CleanDecimal.French('//div[@class="montantEncours"]/text()')(self.doc)

        account.id = '%s-%s' % (parent_account.id, card_infos.group(4))
        account.type = Account.TYPE_CARD
        account.parent = parent_account
        account.balance = Decimal('0')
        account.coming = coming
        account.number = card_infos.group(2)
        account.label = card_info
        account.currency = parent_account.currency
        account._transactions_link = self.format_url(self.url)
        account._transfer_id = None
        # We need to store this url. It will be useful later to get the transactions.
        account._cards_list = self.url
        return account

    def get_child_cards(self, parent_account):
        # There is a selector with only one entry when there is only one card
        # But not when there are multiple card.
        if self.doc.xpath('//select[@id="selectCard"]'):
            return [self.get_single_card(parent_account)]
        return list(self.iter_multi_cards(parent_account=parent_account, cards_list=self.url))

    @method
    class iter_transactions(TableElement):

        item_xpath = '//tr[contains(@class, "ligne")]'
        head_xpath = '//th'

        col_date = re.compile('Date')
        col_label = re.compile('Libellé')
        col_amount = re.compile('Montant')

        class item(ItemElement):
            klass = Transaction

            obj_rdate = obj_bdate = Date(CleanText(TableCell('date')), dayfirst=True)
            obj_type = Transaction.TYPE_DEFERRED_CARD
            obj_raw = obj_label = CleanText(TableCell('label'))
            obj_amount = CleanDecimal.French(TableCell('amount'))

            def obj_date(self):
                return self.page.deferred_date()

            def condition(self):
                if Field('date')(self) < Field('rdate')(self):
                    self.logger.error(
                        'skipping transaction with rdate(%s) > date(%s) for label(%s)',
                        Field('rdate')(self), Field('date')(self), Field('label')(self)
                    )
                    return False
                return True


MARKET_TRANSACTION_TYPES = {
    'VIREMENT': Transaction.TYPE_TRANSFER,
}


class BoursePage(LoggedPage, HTMLPage):
    ENCODING = 'latin-1'
    REFRESH_MAX = 0

    TYPES = {
        'plan épargne en actions': Account.TYPE_PEA,
        "plan d'épargne en actions": Account.TYPE_PEA,
        'plan épargne en actions bourse': Account.TYPE_PEA,
        "plan d'épargne en actions bourse": Account.TYPE_PEA,
        'pea pme bourse': Account.TYPE_PEA,
        'pea pme': Account.TYPE_PEA,
    }

    def on_load(self):
        """
        Sometimes we are directed towards a prior html page before accessing Bourse Page.
        Submit the form to access the page that contains the Bourse Page's session cookie.
        """
        try:
            form = self.get_form(id='form')
        except FormNotFound:  # already on the targetted page
            pass
        else:
            form.submit()

        super(BoursePage, self).on_load()

    def open_iframe(self):
        # should be done always (in on_load)?
        for iframe in self.doc.xpath('//iframe[@id="mainIframe"]'):
            self.browser.location(iframe.attrib['src'])
            break

    def password_required(self):
        return CleanText(
            '//b[contains(text(), "Afin de sécuriser vos transactions, nous vous invitons à créer un mot de passe trading")]'
        )(self.doc)

    def get_next(self):
        if 'onload' in self.doc.xpath('.//body')[0].attrib:
            return re.search('"(.*?)"', self.doc.xpath('.//body')[0].attrib['onload']).group(1)

    def get_fullhistory(self):
        form = self.get_form(id="historyFilter")
        form['cashFilter'] = "ALL"
        # We can't go above 2 years
        form['beginDayfilter'] = (
            datetime.strptime(form['endDayfilter'], '%d/%m/%Y') - timedelta(days=730)
        ).strftime('%d/%m/%Y')
        form.submit()

    @method
    class get_list(TableElement):
        item_xpath = '//table[has-class("tableau_comptes_details")]//tr[td and not(parent::tfoot)]'
        head_xpath = '//table[has-class("tableau_comptes_details")]/thead/tr/th'

        col_label = 'Comptes'
        col_owner = re.compile('Titulaire')
        col_titres = re.compile('Valorisation')
        col_especes = re.compile('Solde espèces')

        class item(OwnedItemElement):
            klass = Account

            load_details = Field('_market_link') & AsyncLoad

            obj__especes = CleanDecimal(TableCell('especes'), replace_dots=True, default=0)
            obj__titres = CleanDecimal(TableCell('titres'), replace_dots=True, default=0)
            obj_valuation_diff = Async('details') & CleanDecimal(
                '//td[contains(text(), "value latente")]/following-sibling::td[1]',
                replace_dots=True,
            )
            obj__market_id = Regexp(Attr(TableCell('label'), 'onclick'), r'nump=(\d+:\d+)')
            obj__market_link = Regexp(Attr(TableCell('label'), 'onclick'), r"goTo\('(.*?)'")
            obj__link_id = Async('details') & Link(u'//a[text()="Historique"]')
            obj__transfer_id = None
            obj_balance = Field('_titres')
            obj_currency = Currency(CleanText(TableCell('titres')))

            def obj_number(self):
                number = CleanText((TableCell('label')(self)[0]).xpath('./div[not(b)]'))(self).replace(' - ', '')
                m = re.search(r'(\d{11,})[A-Z]', number)
                if m:
                    number = m.group(0)
                return number

            def obj_id(self):
                return "%sbourse" % Field('number')(self)

            def obj_label(self):
                return "%s Bourse" % CleanText((TableCell('label')(self)[0]).xpath('./div[b]'))(self)

            def obj_type(self):
                _label = ' '.join(Field('label')(self).split()[:-1]).lower()
                for key in self.page.TYPES:
                    if key in _label:
                        return self.page.TYPES.get(key)
                return Account.TYPE_MARKET

            def obj_ownership(self):
                owner = CleanText(TableCell('owner'))(self)
                return self.get_ownership(owner)

    def get_logout_link(self):
        return Link('//a[contains(text(), "Retour aux comptes")]')(self.doc)

    @method
    class iter_investment(TableElement):
        item_xpath = '//table[@id="tableValeurs"]/tbody/tr[@id and count(descendant::td) > 1]'
        head_xpath = '//table[@id="tableValeurs"]/thead/tr/th'

        col_label = 'Valeur / Isin'
        col_quantity = re.compile('Quantit|Qt')
        col_unitprice = re.compile(r'Prix de revient')
        col_unitvalue = 'Cours'
        col_valuation = re.compile(r'Val(.*)totale')  # 'Val. totale' or 'Valorisation totale'
        col_diff = re.compile(r'\+/- Value latente')
        col_diff_percent = 'Perf'

        class item(ItemElement):
            klass = Investment

            obj_label = Base(TableCell('label'), CleanText('./following-sibling::td[1]//a'))
            obj_code = Base(
                TableCell('label'),
                IsinCode(
                    Regexp(
                        CleanText('./following-sibling::td[1]//br/following-sibling::text()', default=NotAvailable),
                        pattern='^([^ ]+).*',
                        default=NotAvailable
                    ),
                    default=NotAvailable
                ),
            )
            obj_code_type = IsinType(Field('code'))
            obj_quantity = Base(
                TableCell('quantity'),
                CleanDecimal.French('./span', default=NotAvailable),
            )
            obj_diff = Base(
                TableCell('diff'),
                CleanDecimal.French('./span', default=NotAvailable),
            )
            # In some cases (some PEA at least) valuation column is missing
            obj_valuation = CleanDecimal.French(TableCell('valuation', default=''), default=NotAvailable)

            def obj_diff_ratio(self):
                if TableCell('diff_percent', default=None)(self):
                    diff_percent = Base(
                        TableCell('diff_percent'),
                        CleanDecimal.French('.//span', default=NotAvailable),
                    )(self)
                    if not empty(diff_percent):
                        return diff_percent / 100
                return NotAvailable

            def obj_original_currency(self):
                unit_value = Base(
                    TableCell('unitvalue'), CleanText('./br/preceding-sibling::text()', default=NotAvailable)
                )(self)
                if "%" in unit_value:
                    return NotAvailable

                currency = Base(
                    TableCell('unitvalue'), Currency('./br/preceding-sibling::text()', default=NotAvailable)
                )(self)
                if currency == Env('account_currency')(self):
                    return NotAvailable
                return currency

            def obj_unitvalue(self):
                # In the case where the account currency is different from the investment one
                if Field('original_currency')(self):
                    return NotAvailable
                unit_value = Base(
                    TableCell('unitvalue'), CleanText('./br/preceding-sibling::text()', default=NotAvailable)
                )(self)
                # Check if the unitvalue and unitprice are in percentage
                if "%" in unit_value and "%" in CleanText(TableCell('unitprice', default=''))(self):
                    # In the unitprice of the page, there can be a value in percent
                    # and still return NotAvailable due to parsing failure
                    # (if it happens, a new case need to be treated)
                    if not Field('unitprice')(self):
                        return NotAvailable
                    # Convert the percentage to ratio
                    # So the valuation can be equal to quantity * unitvalue
                    return Eval(
                        lambda x: x / 100,
                        Base(TableCell('unitvalue'), CleanDecimal.French('./br/preceding-sibling::text()'))(self)
                    )(self)

                return Base(
                    TableCell('unitvalue'), CleanDecimal.French('./br/preceding-sibling::text()', default=NotAvailable)
                )(self)

            def obj_original_unitvalue(self):
                if not Field('original_currency')(self):
                    return NotAvailable
                return Base(
                    TableCell('unitvalue'),
                    CleanDecimal.French('./br/preceding-sibling::text()', default=NotAvailable)
                )(self)

            def obj_unitprice(self):
                unit_value = Base(
                    TableCell('unitvalue'), CleanText('./br/preceding-sibling::text()', default=NotAvailable)
                )(self)
                if "%" in unit_value and "%" in CleanText(TableCell('unitprice', default=''))(self):
                    # unit price (in %) is displayed like this : 1,00 (100,00%)
                    # Retrieve only the first value.
                    return CleanDecimal.French(
                        Regexp(
                            CleanText(TableCell('unitprice')),
                            pattern='^(\\d+),(\\d+)',
                            default=''
                        ),
                        default=NotAvailable
                    )(self)
                # Sometimes (for some PEA at least) unitprice column isn't returned by LCL
                return CleanDecimal.French(TableCell('unitprice', default=NotAvailable))(self)

    @pagination
    @method
    class iter_history(TableElement):
        item_xpath = '//table[@id="historyTable" and thead]/tbody/tr'
        head_xpath = '//table[@id="historyTable" and thead]/thead/tr/th'

        col_date = 'Date'
        col_label = u'Opération'
        col_quantity = u'Qté'
        col_code = u'Libellé'
        col_amount = 'Montant'

        def next_page(self):
            form = self.page.get_form(id="historyFilter")
            form['PAGE'] = int(form['PAGE']) + 1
            if self.page.doc.xpath('//*[@data-page = $page]', page=form['PAGE']):
                return requests.Request("POST", form.url, data=dict(form))

        class item(ItemElement):
            klass = Transaction

            obj_date = Date(CleanText(TableCell('date')), dayfirst=True)
            obj_type = MapIn(Field('label'), MARKET_TRANSACTION_TYPES, Transaction.TYPE_BANK)
            obj_amount = CleanDecimal(TableCell('amount'), replace_dots=True)
            obj_investments = Env('investments')

            def obj_label(self):
                return TableCell('label')(self)[0].xpath('./text()')[0].strip()

            def parse(self, el):
                i = None
                self.env['investments'] = []

                if CleanText(TableCell('code'))(self):
                    i = Investment()
                    i.label = Field('label')(self)
                    i.code = TableCell('code')(self)[0].xpath('./text()[last()]')[0].strip()
                    i.quantity = CleanDecimal.French(TableCell('quantity'), default=NotAvailable)(self)
                    i.valuation = Field('amount')(self)
                    i.vdate = Field('date')(self)

                    self.env['investments'] = [i]


MARKET_ORDER_DIRECTIONS = {
    'Achat': MarketOrderDirection.BUY,
    'Vente': MarketOrderDirection.SALE,
}

MARKET_ORDER_TYPES = {
    'marché': MarketOrderType.MARKET,
    'déclenchement': MarketOrderType.TRIGGER,
    'limit': MarketOrderType.LIMIT,
}


class MarketOrdersPage(LoggedPage, HTMLPage):
    ENCODING = 'latin-1'
    REFRESH_MAX = 0

    def get_daterange_params(self):
        form = self.get_form(id='orderFilter')
        # Max history is one year
        form['ORDER_UPDDTMIN'] = (datetime.today() - relativedelta(years=1)).strftime('%d/%m/%Y')
        # Sort by creation instead of last update
        form['champsTri'] = 'CREATION_DT'
        return dict(form)

    def get_last_page_index(self):
        last_page_index = CleanDecimal.SI(
            Attr('//td[@class="pagination-right-cursor"]', 'data-page', default=NotAvailable),
            default=NotAvailable
        )(self.doc)
        if last_page_index:
            return int(last_page_index)
        return 1

    @method
    class iter_market_orders(TableElement):
        item_xpath = '//table[@id="orderListTable"]/tbody/tr[count(td)>1]'
        head_xpath = '//table[@id="orderListTable"]//th'

        col_details_link = 'Détails'
        col_date = 'Date de création'
        col_label = 'Libellé'
        col_direction = 'Sens'
        col_quantity = 'Qté'
        col_ordervalue_limit = 'Limite'
        col_ordervalue_trigger = 'Seuil'
        col_state_unitprice = 'Etat'
        col_validity_date = 'Date de validité'

        class item(ItemElement):
            klass = MarketOrder

            obj__details_link = Base(TableCell('details_link'), Link('.//a'))
            obj_date = Date(Regexp(CleanText(TableCell('date')), r'^(.+?) '), dayfirst=True)
            obj_label = Base(TableCell('label'), Attr('.//a', 'title'))
            obj_code = Base(
                TableCell('label'),
                IsinCode(Regexp(Attr('.//a', 'href'), r"goQuote\('(.+?)'"), default=NotAvailable)
            )
            obj_direction = MapIn(
                CleanText(TableCell('direction')),
                MARKET_ORDER_DIRECTIONS,
                MarketOrderDirection.UNKNOWN
            )
            obj_quantity = CleanDecimal.French(TableCell('quantity'), default=NotAvailable)
            obj_ordervalue = Coalesce(
                CleanDecimal.French(TableCell('ordervalue_limit'), default=NotAvailable),
                CleanDecimal.French(TableCell('ordervalue_trigger'), default=NotAvailable),
                default=NotAvailable
            )
            obj_state = Regexp(CleanText(TableCell('state_unitprice')), r'(.+?)(?: à|$)', default=NotAvailable)
            obj_unitprice = CleanDecimal.French(TableCell('state_unitprice'), default=NotAvailable)
            obj_validity_date = Date(CleanText(TableCell('validity_date')), dayfirst=True, default=NotAvailable)

    @method
    class fill_market_order(ItemElement):
        obj_id = CleanText('//td[contains(text(), "Référence Bourse")]/following-sibling::td[1]')
        obj_amount = CleanDecimal.French(
            '//td[contains(text(), "Total")]/following-sibling::td[1]',
            default=NotAvailable
        )
        obj_currency = Coalesce(
            Currency('//td[contains(text(), "Seuil")]/following-sibling::td[1]', default=NotAvailable),
            Currency('//td[contains(text(), "Montant brut")]/following-sibling::td[1]', default=NotAvailable),
            default=NotAvailable
        )
        obj_order_type = MapIn(
            Lower(CleanText('//td[contains(text(), "Modalité")]/following-sibling::td[1]')),
            MARKET_ORDER_TYPES,
            MarketOrderType.UNKNOWN
        )
        obj_stock_market = Regexp(
            CleanText('//td[contains(text(), "Place")]/following-sibling::td[1]'),
            r'(.+) \(',
            default=NotAvailable
        )


class DiscPage(LoggedPage, HTMLPage):
    def on_load(self):
        try:
            # when life insurance access is restricted, a complete lcl logout form is present, don't use it
            # and sometimes there's just no form
            form = self.get_form(xpath='//form[not(@id="formLogout")]')
            form.submit()
        except FormNotFound:
            # Sometime no form is present, just a redirection
            self.logger.debug('no form on this page')

        super(DiscPage, self).on_load()


class NoPermissionPage(LoggedPage, HTMLPage):
    def get_error_msg(self):
        error_msg = CleanText(
            '//div[@id="divContenu"]//div[@id="attTxt" and contains(text(), "vous n\'avez pas accès à cette opération")]'
        )(self.doc)
        return error_msg


class AVNotAuthorized(LoggedPage, HTMLPage):
    pass


class AVReroute(LoggedPage, HTMLPage):
    pass


class CookiesAcceptancePage(LoggedPage, HTMLPage):
    def handle_cookies(self):
        form = self.get_form(id='form1')
        form[Attr('//button[@id="MainMasterContainer_BTN_Deny"]', 'name')(self.doc)] = ''
        form.submit()


class AVPage(LoggedPage, HTMLPage):
    def get_routage_url(self):
        for account in self.doc.xpath('//table[@class]/tbody/tr'):
            if account.xpath('.//td[has-class("nomContrat")]//a[has-class("routageCAR")]'):
                return Link('.//td[has-class("nomContrat")]//a[has-class("routageCAR")]')(account)

    def is_website_life_insurance(self):
        # no need specific account to go on life insurance external website
        # because we just need to go on life insurance external website
        return bool(self.get_routage_url())

    def get_calie_life_insurances_first_index(self):
        # indices are associated to calie life insurances to make requests to them
        # if only one life insurance, this request directly leads to details on CaliePage
        # otherwise, any index will lead to CalieContractsPage,
        # so we stop at the first index
        for account in self.doc.xpath('//table[@class]/tbody/tr'):
            if account.xpath('.//td[has-class("nomContrat")]//a[contains(@class, "redirect")][@href="#"]'):
                index = Attr(
                    account.xpath('.//td[has-class("nomContrat")]//a[contains(@class, "redirect")][@href="#"]'),  # wtf
                    'id'
                )(self)
                return index

    @method
    class get_popup_life_insurance(ListElement):
        item_xpath = '//table[@class]/tbody/tr'

        class item(OwnedItemElement):
            klass = Account

            def condition(self):
                if self.obj_balance(self) == 0 and not self.el.xpath('.//td[has-class("nomContrat")]//a'):
                    self.logger.warning("ignoring an AV account because there's no link for it")
                    return False
                # there is life insurance detail page link but check if it's a popup
                return self.el.xpath('.//td[has-class("nomContrat")]//a[has-class("clickPopupDetail")]')

            obj__owner = CleanText('.//td[2]')
            obj_label = Format(u'%s %s', CleanText('.//td/text()[following-sibling::br]'), obj__owner)
            obj_balance = CleanDecimal('.//td[last()]', replace_dots=True)
            obj_type = Account.TYPE_LIFE_INSURANCE
            obj_currency = 'EUR'
            obj__link_id = None
            obj__market_link = None
            obj__coming_links = []
            obj__transfer_id = None
            obj_number = Field('id')
            obj__external_website = False
            obj__is_calie_account = False

            def obj_ownership(self):
                owner = CleanText(Field('_owner'))(self)
                return self.get_ownership(owner)

            def parse(self, el):
                _id = CleanText('.//td/@id')(self)
                # in old code, we use _id, it seems that is not used anymore
                # but check if it's the case for all users
                assert not _id, '_id is still used to retrieve life insurance'

                try:
                    self.page.browser.assurancevie.go()
                    ac_details_page = self.page.browser.open(Link('.//td[has-class("nomContrat")]//a')(self)).page
                    self.env['id'] = CleanText(
                        './/td[contains(text(), "Numéro de contrat")]/following-sibling::td[1]'
                    )(ac_details_page.doc)
                    self.env['opening_date'] = Date(
                        CleanText('.//td[contains(text(), "Date d\'effet")]/following-sibling::td[1]'),
                        dayfirst=True,
                        default=NotAvailable,
                    )(ac_details_page.doc)
                except ServerError:
                    self.logger.debug("link didn't work, trying with the form instead")
                    # the above server error can cause the form to fail,
                    # so we may have to go back on the accounts list before submitting
                    self.page.browser.open(self.page.url)
                    # redirection to lifeinsurances accounts and comeback on Lcl original website
                    page = self.obj__form().submit().page
                    # Getting the account details from the JSON containing the account information:
                    details_page = self.page.browser.open(BrowserURL('av_investments')(self)).page
                    account_id = Dict('situationAdministrativeEpargne/idcntcar')(details_page.doc)
                    page.come_back()
                    self.env['id'] = account_id
                    self.env['opening_date'] = NotAvailable

            obj_id = Env('id')
            obj_opening_date = Env('opening_date')

            def obj__form(self):
                # maybe deprecated
                form_id = Attr('.//td[has-class("nomContrat")]//a', 'id', default=None)(self)
                if form_id:
                    if '-' in form_id:
                        id_contrat = re.search(r'^(.*?)-', form_id).group(1)
                        producteur = re.search(r'-(.*?)$', form_id).group(1)
                    else:
                        id_contrat = form_id
                        producteur = None
                else:
                    if len(self.xpath('.//td[has-class("nomContrat")]/a[has-class("clickPopupDetail")]')):
                        # making a form of this link sometimes makes the site return an empty response...
                        # the link is a link to some info, not full AV website
                        # it's probably an indication the account is restricted anyway, so avoid it
                        self.logger.debug("account is probably restricted, don't try its form")
                        return None

                    # sometimes information are not in id but in href
                    url = Attr('.//td[has-class("nomContrat")]//a', 'href', default=None)(self)
                    parsed_url = urlparse(url)
                    params = parse_qs(parsed_url.query)

                    id_contrat = params['ID_CONTRAT'][0]
                    producteur = params['PRODUCTEUR'][0]

                if self.xpath('//form[@id="formRedirectPart"]'):
                    form = self.page.get_form('//form[@id="formRedirectPart"]')
                else:
                    form = self.page.get_form('//form[@id="formRoutage"]')
                    form['PRODUCTEUR'] = producteur
                form['ID_CONTRAT'] = id_contrat
                return form


class CalieContractsPage(LoggedPage, HTMLPage):
    @method
    class iter_calie_life_insurance(TableElement):
        head_xpath = '//table[contains(@id, "MainTable")]//tr[contains(@id, "HeadersRow")]//td[text()]'
        item_xpath = '//table[contains(@id, "MainTable")]//tr[contains(@id, "DataRow")]'

        col_number = 'Numéro contrat'  # internal contrat number

        class item(ItemElement):
            klass = Account

            # internal contrat number, to be replaced by external number in CaliePage.fill_account()
            # obj_id is needed here though, to avoid dupicate account errors
            obj_id = CleanText(TableCell('number'))

            obj_url = AbsoluteLink('.//a')  # need AbsoluteLink since we moved out of basurl domain
            obj__market_link = None


class SendTokenPage(LoggedPage, LCLBasePage):
    def on_load(self):
        form = self.get_form('//form')
        return form.submit()


class Form2Page(LoggedPage, LCLBasePage):
    def assurancevie_hist_not_available(self):
        msg = "Ne détenant pas de compte dépôt chez LCL, l'accès à ce service vous est indisponible"
        return msg in CleanText('//div[@id="attTxt"]')(self.doc)

    def on_load(self):
        if self.assurancevie_hist_not_available():
            return
        error = CleanText('//div[@id="attTxt"]/text()[1]')(self.doc)
        if "L’accès au service est momentanément indisponible" in error:
            raise BrowserUnavailable(error)
        form = self.get_form()
        return form.submit()


class CalieTableElement(TableElement):
    # We need to set the first column to 1 otherwise
    # there is a shift between column titles and contents
    def get_colnum(self, name):
        return super(CalieTableElement, self).get_colnum(name) + 1


class CaliePage(LoggedPage, HTMLPage):
    def check_error(self):
        message = CleanText(
            '//div[contains(@class, "disclaimer-div")]//text()[contains(., "utilisation vaut acceptation")]'
        )(self.doc)
        if self.doc.xpath('//button[@id="acceptDisclaimerButton"]') and message:
            raise ActionNeeded(message)

    @method
    class iter_investment(CalieTableElement):
        # Careful, <table> contains many nested <table/tbody/tr/td>
        # Two first lines are titles, two last are investment sum-ups
        item_xpath = '//table[@class="dxgvTable dxgvRBB"]//tr[contains(@class, "DataRow")]'
        head_xpath = '//table[contains(@id, "MainTable")]//tr[contains(@id, "HeadersRow")]//td[text()]'

        col_label = 'Support'
        col_vdate = 'Date de valeur'
        col_original_valuation = 'Valeur dans la devise du support'
        col_valuation = 'Valeur dans la devise du support (EUR)'
        col_unitvalue = 'Valeur unitaire'
        col_quantity = 'Parts'
        col_diff_ratio = 'Performance'
        col_portfolio_share = 'Répartition (%)'

        class item(ItemElement):
            klass = Investment

            obj_label = CleanText(TableCell('label'))
            obj_original_valuation = CleanDecimal(TableCell('original_valuation'), replace_dots=True)
            obj_valuation = CleanDecimal(TableCell('valuation'), replace_dots=True)
            obj_vdate = Date(CleanText(TableCell('vdate')), dayfirst=True)
            obj_unitvalue = CleanDecimal(
                TableCell('unitvalue'), replace_dots=True, default=NotAvailable
            )  # displayed with format '123.456,78 EUR'
            obj_quantity = CleanDecimal(
                TableCell('quantity'), replace_dots=True, default=NotAvailable)  # displayed with format '1.234,5678 u.'
            obj_portfolio_share = Eval(lambda x: x / 100, CleanDecimal(TableCell('portfolio_share')))

            def obj_diff_ratio(self):
                _diff_ratio = CleanDecimal(TableCell('diff_ratio'), default=NotAvailable)(self)
                if not empty(_diff_ratio):
                    return Eval(lambda x: x / 100, _diff_ratio)(self)
                return NotAvailable

            # Unfortunately on the Calie space the links to invest details return Forbidden even on the website
            obj_code = NotAvailable
            obj_code_type = NotAvailable

    @method
    class fill_account(ItemElement):
        obj_number = obj_id = Regexp(CleanText('.'), r'Numéro externe (.{10})')
        obj_label = Format(
            '%s %s',
            Regexp(CleanText('.'), r'Produit (.*) Statut'),
            Field('id')
        )
        obj_balance = CleanDecimal('//tr[contains(@id, "FooterRow")]', replace_dots=True)
        obj_type = Account.TYPE_LIFE_INSURANCE
        obj_currency = 'EUR'
        obj__external_website = True
        obj__is_calie_account = True
        obj__transfer_id = None

        def obj__history_url(self):
            relative_url = Regexp(Attr('//a[contains(text(), "Opérations")]', 'onclick'), r'href=\'(.*)\'')(self)
            return urljoin(self.page.url, relative_url)


class AVDetailPage(LoggedPage, LCLBasePage):
    def come_back(self):
        session = self.get_from_js('idSessionSag = "', '"')
        params = {}
        params['sessionSAG'] = session
        params['stbpg'] = 'pagePU'
        params['act'] = ''
        params['typeaction'] = 'reroutage_retour'
        params['site'] = 'LCLI'
        params['stbzn'] = 'bnc'
        return self.browser.location(
            'https://assurance-vie-et-prevoyance.secure.lcl.fr/filiale/entreeBam',
            params=params
        )


class AVListPage(LoggedPage, JsonPage):
    @method
    class iter_life_insurance(DictElement):
        item_xpath = 'syntheseContrats'

        class item(ItemElement):
            def condition(self):
                activity = Dict('lcstacntgen')(self)
                account_type = Dict('lcgampdt')(self)
                # We ignore accounts without activities or when the activity is 'Closed',
                # they are inactive and closed, and they don't appear on the website.
                return bool(
                    activity and account_type
                    and activity.lower() == 'actif'
                    and account_type.lower() == 'epargne'
                )

            klass = Account

            obj_id = obj_number = Dict('idcntcar')
            obj_balance = CleanDecimal(Dict('mtvalcnt'))
            obj_label = Dict('lnpdt')
            obj_type = Account.TYPE_LIFE_INSURANCE
            obj_currency = 'EUR'
            obj_opening_date = Date(Dict('dbcnt'))

            obj__external_website = True
            obj__form = None
            obj__link_id = None
            obj__market_link = None
            obj__coming_links = []
            obj__transfer_id = None
            obj__is_calie_account = False


class AVHistoryPage(LoggedPage, JsonPage):
    @method
    class iter_history(DictElement):
        item_xpath = 'listeOperations'

        class item(ItemElement):
            klass = Transaction

            obj_label = CleanText(Dict('lcope'))
            obj_amount = CleanDecimal(Dict('mtope'))
            obj_type = Transaction.TYPE_BANK
            obj_investments = NotAvailable

            # The 'idope' key contains a string such as "70_ABC666ABC   2018-03-182018-03-16-20.55.27.960852"
            # 70= N° transaction, 6660666= N° account, 2018-03-18= date and 2018-03-16=rdate.
            # We thus use "70_ABC666ABC" for the transaction ID.

            obj_id = Regexp(CleanText(Dict('idope')), r'(\d+_[\dA-Z]+)')

            def obj__dates(self):
                raw = CleanText(Dict('idope'))(self)
                m = re.findall(r'\d{4}-\d{2}-\d{2}', raw)
                # We must verify that the two dates are correctly fetched
                assert len(m) == 2
                return m

            def obj_date(self):
                return Date().filter(Field('_dates')(self)[0])

            def obj_rdate(self):
                return Date().filter(Field('_dates')(self)[1])


class AVInvestmentsPage(LoggedPage, JsonPage):
    def update_life_insurance_account(self, life_insurance):
        life_insurance._owner = Format(
            '%s %s',
            Dict('situationAdministrativeEpargne/lppeoscp'),
            Dict('situationAdministrativeEpargne/lnpeoscp'),
        )(self.doc)
        life_insurance.label = '%s %s' % (
            Dict('situationAdministrativeEpargne/lcofc')(self.doc),
            life_insurance._owner,
        )
        life_insurance.valuation_diff = CleanDecimal(
            Dict('situationFinanciereEpargne/mtpmvcnt'),
            default=NotAvailable
        )(self.doc)
        return life_insurance

    @method
    class iter_investment(DictElement):
        item_xpath = 'listeSupports/support'

        class item(ItemElement):
            klass = Investment

            obj_label = CleanText(Dict('lcspt'))
            obj_valuation = CleanDecimal(Dict('mtvalspt'))
            obj_code = CleanText(Dict('cdsptisn'), default=NotAvailable)
            obj_unitvalue = CleanDecimal(Dict('mtliqpaaspt'), default=NotAvailable)
            obj_quantity = CleanDecimal(Dict('qtpaaspt'), default=NotAvailable)
            obj_diff = CleanDecimal(Dict('mtpmvspt'), default=NotAvailable)
            obj_vdate = Date(Dict('dvspt'), default=NotAvailable)
            obj_code_type = IsinType(Field('code'))

            def obj_portfolio_share(self):
                ptf = CleanDecimal(Dict('txrpaspt'), default=NotAvailable)(self)
                ptf /= 100
                return ptf


class RibPage(LoggedPage, LCLBasePage):
    def get_iban(self):
        if self.doc.xpath(
            '//div[contains(@class, "rib_cadre")]//div[contains(@class, "rib_internat")]'
        ):
            return CleanText(
                '//div[contains(@class, "rib_cadre") and not(contains(@class, "hidden"))]//div[contains(@class, "rib_internat")]//p//strong/text()[1]',
                replace=[(' ', '')]
            )(self.doc)

    def check_iban_by_account(self, account_id):
        iban_account_id = CleanText().filter(
            self.doc.xpath('(//td[@class[contains(., "guichet-")]]/following-sibling::*)[1]/strong'))
        iban_guichet_id = CleanText().filter(self.doc.xpath('(//td[@class[contains(., "guichet-")]]/strong)[1]'))
        iban_account = "%s%s" % (iban_guichet_id, iban_account_id[4:])

        if account_id == iban_account:
            return CleanText(
                '//div[contains(@class, "rib_cadre") and not(contains(@class, "hidden"))]//div[contains(@class, "rib_internat")]//p//strong/text()[1]',
                replace=[(' ', '')]
            )(self.doc)

        return None

    def has_iban_choice(self):
        return not bool(
            self.doc.xpath('(//strong[contains(., "RELEVE D\'IDENTITE BANCAIRE")])[1]')
        )


class HomePage(LoggedPage, HTMLPage):
    pass


class TransferPage(LoggedPage, HTMLPage):
    def on_load(self):
        # This aims to track input errors.
        script_error = CleanText(u"//script[contains(text(), 'if (\"true\"===\"true\")')]")(self.doc)
        if script_error:
            html = re.search(r'\.html\("(.*?)"\)', script_error).group(1)
            message = CleanText().filter(html2text(html))  # wtf?
            raise TransferBankError(message=message)

    def can_transfer(self, account_transfer_id):
        for div in self.doc.xpath('//div[input[@id="indexCompteEmetteur"]]//div[@class="infoCompte" and not(@title)]'):
            if account_transfer_id in CleanText('.', replace=[(' ', '')])(div):
                return True
        return False

    def get_account_index(self, xpath, account_id):
        for option in self.doc.xpath('//select[@id=$id]/option', id=xpath):
            if account_id in CleanText('.', replace=[(' ', '')])(option):
                return option.attrib['value']
        else:
            raise TransferError("account %s not found" % account_id)

    def choose_recip(self, recipient):
        form = self.get_form(id='formulaire')
        form['indexCompteDestinataire'] = self.get_value(recipient._transfer_id, 'recipient')
        form.submit()

    def transfer(self, amount, reason):
        form = self.get_form(id='formulaire')
        form['libMontant'] = amount
        form['motifVirement'] = reason
        form.submit()

    def deferred_transfer(self, amount, reason, exec_date):
        form = self.get_form(id='formulaire')
        form['libMontant'] = amount
        form['motifVirement'] = reason
        form['libDateProg'] = exec_date.strftime('%d/%m/%Y')
        form['dateFinVirement'] = 'N'
        form['frequenceVirement'] = 'UD'
        form['premierJourVirementProg'] = '01'
        form['typeVirement'] = 'Programme'
        form.submit()

    def check_transfer_error(self):
        err_msg = CleanText('//span[@id="virementErrorsTexte"]')(self.doc)
        if err_msg:
            raise TransferBankError(message=err_msg)

    def get_id_from_response(self, acc):
        id_xpath = '//div[@id="contenuPageVirement"]//div[@class="infoCompte" and not(@title)]'
        acc_ids = [CleanText('.')(acc_id) for acc_id in self.doc.xpath(id_xpath)]
        # there should have 2 ids, one for account and one for recipient
        assert len(acc_ids) == 2

        for index, acc_id in enumerate(acc_ids):
            _id = acc_id.split(' ')
            if len(_id) == 2:
                # to match with woob account id
                acc_ids[index] = _id[0] + _id[1][4:]

        if acc == 'account':
            return acc_ids[0]
        return acc_ids[1]

    def handle_response(self, account, recipient):
        self.check_transfer_error()

        transfer = Transfer()

        transfer._account = account
        transfer.account_id = self.get_id_from_response('account')
        transfer.account_iban = account.iban
        transfer.account_label = account.label
        transfer.account_balance = account.balance
        assert (
            account._transfer_id in CleanText(
                '//div[div[@class="libelleChoix" and contains(text(), "Compte émetteur")]]//div[@class="infoCompte" and not(@title)]',
                replace=[(' ', '')]
            )(self.doc)
        )

        transfer._recipient = recipient
        transfer.recipient_id = self.get_id_from_response('recipient')
        transfer.recipient_iban = recipient.iban
        transfer.recipient_label = recipient.label
        assert (
            recipient._transfer_id in CleanText(
                '//div[div[@class="libelleChoix" and contains(text(), "Compte destinataire")]]//div[@class="infoCompte" and not(@title)]',
                replace=[(' ', '')]
            )(self.doc)
        )

        transfer.currency = FrenchTransaction.Currency('//div[@class="topBox"]/div[@class="montant"]')(self.doc)
        transfer.amount = CleanDecimal('//div[@class="topBox"]/div[@class="montant"]', replace_dots=True)(self.doc)
        transfer.exec_date = Date(
            Regexp(CleanText('//div[@class="topBox"]/div[@class="date"]'), r'(\d{2}\/\d{2}\/\d{4})'),
            dayfirst=True
        )(self.doc)
        # skip html comment with filtering on text() content
        transfer.label = CleanText(
            '//div[@class="motif"]/text()[contains(., "Motif : ")]',
            replace=[('Motif : ', '')]
        )(self.doc)

        return transfer

    def confirm(self):
        form = self.get_form(id='formulaire')
        form.submit()

    def get_value(self, _id, value_type):
        for div in self.doc.xpath('//div[@onclick]'):
            if _id in CleanText('.//div[not(@title)]', replace=[(' ', '')])(div):
                return Regexp(Attr('.', 'onclick'), r'(\d+)')(div)
        raise TransferError('Could not find %s account.' % value_type)

    def choose_origin(self, account_transfer_id):
        form = self.get_form()
        form['indexCompteEmetteur'] = self.get_value(account_transfer_id, 'origin')
        form.submit()

    @method
    class iter_recipients(ListElement):
        item_xpath = '//div[@id="listeDestinataires"]//div[@class="pointeur cardCompte"]'

        class Item(ItemElement):
            klass = Recipient

            def condition(self):
                return len(self.el.xpath('./div')) > 1

            obj_id = CleanText('./div[@class="infoCompte" and not(@title)]', replace=[(' 0000', '')])
            obj__transfer_id = CleanText('./div[@class="infoCompte" and not(@title)]', replace=[(' ', '')])
            obj_label = CleanText('./div[1]')
            obj_bank_name = Env('bank_name')
            obj_category = Env('category')
            obj_iban = Env('iban')

            def obj_enabled_at(self):
                return datetime.now().replace(microsecond=0)

            def validate(self, obj):
                return Field('id')(self) != self.env['account_transfer_id']

            def parse(self, el):
                if bool(CleanText('./div[@id="soldeEurosCompte"]')(self)):
                    self.env['category'] = u'Interne'
                    account = find_object(self.page.browser.get_accounts_list(), id=self.obj_id(self))

                    self.env['iban'] = NotAvailable
                    if account:
                        self.env['iban'] = account.iban

                    self.env['bank_name'] = u'LCL'
                else:
                    self.env['category'] = u'Externe'
                    self.env['iban'] = self.obj_id(self)
                    self.env['bank_name'] = NotAvailable

    def check_confirmation(self):
        transfer_confirmation_msg = CleanText('//div[@class="alertConfirmationVirement"]')(self.doc)
        assert transfer_confirmation_msg, 'Transfer confirmation message is not found.'


class AddRecipientPage(LoggedPage, HTMLPage):
    def get_error(self):
        error = CleanText('//div[@id="attTxt"]', children=False)(self.doc)
        if error and 'nécessaire afin de vous envoyer un code' in error:
            return error

    def validate(self, iban, label):
        form = self.get_form(id='mainform')
        form['PAYS_IBAN'] = iban[:2]
        form['LIBELLE'] = label
        form['COMPTE_IBAN'] = iban[2:]
        form.submit()


class CheckValuesPage(HTMLPage):
    def get_error(self):
        return CleanText('//div[@id="attTxt"]/p')(self.doc)

    def check_values(self, iban, label):
        # This method is also used in `RecipConfirmPage`.
        # In `CheckValuesPage`, xpath can be like `//strong[@id="iban"]`
        # but not in `RecipConfirmPage`.
        # So, use more generic xpaths which work for the two pages.
        iban_xpath = '//div[label[contains(text(), "IBAN")]]//strong'
        scraped_iban = CleanText(iban_xpath, replace=[(' ', '')])(self.doc)

        label_xpath = '//div[label[contains(text(), "Libellé")]]//strong'
        scraped_label = CleanText(label_xpath)(self.doc)

        assert iban == scraped_iban, 'Recipient Iban changed from (%s) to (%s)' % (iban, scraped_iban)
        assert label == scraped_label, 'Recipient label changed from (%s) to (%s)' % (label, scraped_label)

    def get_authent_mechanism(self):
        if self.doc.xpath('//div[@id="envoiMobile" and @class="selectTel"]'):
            return 'otp_sms'
        elif self.doc.xpath('//script[contains(text(), "AuthentForteDesktop")]'):
            return 'app_validation'

    def get_phone_attributes(self):
        # The number which begin by 06 or 07 is not always referred as MOBILE number
        # this function parse the html tag of the phone number which begins with 06 or 07
        # to determine the canal attributed by the website, it can be MOBILE or FIXE
        phone = {}
        for phone_tag in self.doc.xpath('//div[@class="choixTel"]//div[@class="selectTel"]'):
            phone['attr_id'] = Attr('.', 'id')(phone_tag)
            phone['number'] = CleanText('.//a[@id="fixIpad"]')(phone_tag)
            if phone['number'].startswith('06') or phone['number'].startswith('07'):
                # Let's take the first mobile phone
                # If no mobile phone is available, we take last phone found (ex: 01)
                break
        assert phone['attr_id'], 'no phone found for 2FA'
        canal = re.match('envoi(Fixe|Mobile)', phone['attr_id'])
        assert canal, 'Canal unknown %s' % phone['attr_id']
        phone['attr_id'] = canal.group(1).upper()
        return phone


class DocumentsPage(LoggedPage, HTMLPage):
    def do_search_request(self):
        form = self.get_form(id="rechercherForm")
        form['listePeriode'] = "PERIODE1"
        form['listeFamille'] = "ALL"
        form['debutRec'] = None
        form['finRec'] = None
        form['typeDocFamHidden'] = "ALL"
        form['typeDocSFamHidden'] = None
        form.submit()

    @method
    class get_list(TableElement):
        head_xpath = '//table[@class="dematTab"]/thead/tr/th'
        item_xpath = u'//table[@class="dematTab"]/tbody/tr[./td[@class="dematTab-firstCell"]]'

        ignore_duplicate = True

        col_label = 'Nature de document'
        col_id = 'Type de document'
        col_url = 'Visualiser'
        col_date = 'Date'

        class item(ItemElement):
            klass = Document

            obj_id = Slugify(Format('%s_%s', CleanText(TableCell('id')), CleanText(TableCell('date'))))
            obj_label = Format('%s %s', CleanText(TableCell('label')), CleanText(TableCell('date')))
            obj_date = Date(CleanText(TableCell('date')), dayfirst=True)
            obj_format = "pdf"

            def obj_url(self):
                return Link(TableCell('url')(self)[0].xpath('./a'))(self)

            def obj_type(self):
                if 'Relevé' in Field('label')(self):
                    return DocumentTypes.STATEMENT
                elif 'Bourse' in Field('label')(self):
                    return DocumentTypes.REPORT
                elif ('information' in Field('id')(self)) or ('avis' in Field('id')(self)):
                    return DocumentTypes.NOTICE
                else:
                    return DocumentTypes.OTHER


class ClientPage(LoggedPage, HTMLPage):
    @method
    class get_item(ItemElement):
        klass = Subscription

        obj_id = CleanText('//li[@id="nomClient"]', replace=[('M', ''), ('Mme', ''), (' ', '')])
        obj_label = CleanText('//li[@id="nomClient"]', replace=[('M', ''), ('Mme', '')])
        obj_subscriber = CleanText('//li[@id="nomClient"]', replace=[('M', ''), ('Mme', '')])


class RecipConfirmPage(LoggedPage, CheckValuesPage):
    def is_here(self):
        return CleanText(
            '//div[@id="componentContainer"]//div[contains(text(), "Compte bénéficiaire de virement à ajouter à votre contrat")]',
            default=None
        )(self.doc)


class TwoFAPage(CheckValuesPage):
    def is_here(self):
        return Coalesce(
            CleanText(
                '''//div[@id="componentContainer"]//h1[contains(text(), "BIENVENUE SUR L'ESPACE DE CONNEXION")]'''
            ),
            CleanText('//div[span and contains(text(), "Pour votre sécurité, validez votre opération en attente")]'),
            default=None
        )(self.doc)

    def get_app_validation_msg(self):
        return Coalesce(
            CleanText('//form[@id="formNoSend"]//div[@id="polling"]//div[contains(text(), "application")]'),
            CleanText('//div[span and contains(text(), "Pour votre sécurité, validez votre opération en attente")]'),
            default=''
        )(self.doc)


class RecipientPage(LoggedPage, HTMLPage):
    pass


class SmsPage(HTMLPage):
    def check_otp_error(self, otp_sent=False):
        # This page just contains a value directly:
        # * true/false: for normal cases
        # Or when requesting to trigger the otp (otp_sent==False):
        # * 'OTP_MAX': otp requested too many times
        # * "AuthentSimple": no need for the otp finally
        # Or when sending the otp code:
        # * -1: Code is already expired
        # * 12: ???
        result = CleanText('.', symbols=['"', '\''])(self.doc)
        result = result.lower()

        if result == 'true':
            return True

        if result == 'authentsimple':
            # otp is not needed
            return False

        if result == 'otp_max':
            raise BrowserIncorrectPassword(
                "Aucun code supplémentaire ne peut être envoyé par téléphone suite à un trop grand nombre de tentatives. Veuillez réessayer ultérieurement."
            )

        if result == '-1':
            raise BrowserIncorrectPassword(
                "Le code envoyé par téléphone a expiré."
            )

        if otp_sent:
            raise BrowserIncorrectPassword(
                "Le code saisi ne correspond pas à celui qui vient de vous être envoyé par téléphone. Vérifiez votre code et saisissez-le à nouveau."
            )

        raise AssertionError('Something went wrong with a sent sms otp')


class RecipRecapPage(LoggedPage, CheckValuesPage):
    pass


class ProfilePage(LoggedPage, HTMLPage):
    def get_profile(self, name):
        error_xpath = '//div[contains(text(), "Nous vous invitons à prendre contact avec votre conseiller")]'
        if self.doc.xpath(error_xpath):
            raise ProfileMissing(CleanText(error_xpath, children=False)(self.doc))

        profile = Person()
        profile.name = name
        try:
            profile.email = Attr('//input[@id="textMail"]', 'value', default=NotAvailable)(self.doc)
        except AttributeNotFound:
            pass
        nb = Attr('//input[@id="nbEnfant"]', 'value', default=NotAvailable)(self.doc)
        if nb:
            profile.children = Decimal(nb)
        return profile


class DepositPage(LoggedPage, HTMLPage):
    @method
    class get_list(TableElement):
        head_xpath = '//table/thead/tr/th'
        item_xpath = '//table/tbody/tr[not(@class="tableTrSolde")]'

        col_owner = 'Titulaire'
        col_name = 'Nom du contrat'
        col_balance = 'Capital investi'

        class item(OwnedItemElement):
            klass = Account

            def validate(self, obj):
                return not empty(obj.balance)

            obj_type = Account.TYPE_DEPOSIT
            obj_label = Format('%s %s', CleanText(TableCell('name')), CleanText(TableCell('owner')))
            obj_balance = CleanDecimal.French(TableCell('balance'), default=NotAvailable)
            obj_currency = 'EUR'
            obj__contract = CleanText(TableCell('name'))
            obj__link_index = Regexp(CleanText('.//a/@id'), r'(\d+)')
            # So it can be modified later
            obj_id = None
            obj__transfer_id = None
            obj__market_link = None

            def obj_ownership(self):
                owner = CleanText(TableCell('owner'))(self)
                return self.get_ownership(owner)

    def set_deposit_account_id(self, account):
        account.id = CleanText('//td[contains(text(), "N° contrat")]/following::td[1]//b')(self.doc)


class AuthentStatusPage(JsonPage):
    def get_status(self):
        return self.doc['status']


class FinalizeTwoFAPage(HTMLPage):
    pass


class RealEstateInvestmentsPage(LoggedPage, HTMLPage):
    @method
    class iter_accounts(TableElement):
        head_xpath = '//table[contains(@summary, "diversification patrimoniale")]/thead/tr/th'
        item_xpath = '//table[contains(@summary, "diversification patrimoniale")]/tbody//tr'

        col_owner = 'Titulaire(s) du compte'
        col_number = 'Indicatif - N° de compte'
        col_balance = 'Valorisation (en €)'
        col_label = 'Nom du placement'
        col_quantity = 'Nombre de parts'
        col_vdate = 'Date de valorisation'
        col_unitvalue = 'Prix de la part (en €)'
        col_category = 'Famille'

        class item(ItemElement):
            klass = Account

            obj_number = CleanText(TableCell('number'), replace=[(' - ', '')])
            obj_type = Account.TYPE_REAL_ESTATE
            obj_label = CleanText(TableCell('label'))
            obj_balance = CleanDecimal.French(TableCell('balance'), default=NotAvailable)
            obj_currency = 'EUR'
            obj__contract = None
            obj__transfer_id = None
            obj__market_link = None

            def obj_id(self):
                return re.sub(' ', '', Format('%s_%s_patrimoine', Field('number'), Field('label'))(self))

            def obj_ownership(self):
                owner = CleanText(TableCell('owner'))(self)
                name = Env('name')(self)
                # We count how many times the last_name is found.
                if len(re.findall(name.split()[-1], owner, re.IGNORECASE)) > 1:
                    return AccountOwnership.CO_OWNER
                return AccountOwnership.OWNER

            def obj__investment(self):
                inv = Investment()
                inv.label = Field('label')(self)
                inv.unitvalue = CleanDecimal.French(CleanText(TableCell('unitvalue'), children=False))(self)
                inv.quantity = CleanDecimal.French(TableCell('quantity'))(self)
                inv.valuation = Field('balance')(self)
                inv.vdate = Date(CleanText(TableCell('vdate')), dayfirst=True)(self)
                inv.asset_category = CleanText(TableCell('category'))(self)

                return [inv]
